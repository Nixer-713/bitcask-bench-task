#!/usr/bin/env python3
import json
import os
import sys
import tempfile


SEGMENT_PREFIX = "segment-"
SEGMENT_SUFFIX = ".log"
DEFAULT_MAX_SEGMENT_BYTES = 1024 * 1024


class StoreError(Exception):
    pass


def compact_json(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def segment_number(name):
    if not (name.startswith(SEGMENT_PREFIX) and name.endswith(SEGMENT_SUFFIX)):
        return None
    middle = name[len(SEGMENT_PREFIX) : -len(SEGMENT_SUFFIX)]
    if not middle.isdigit():
        return None
    return int(middle)


class KVStore:
    def __init__(self, dbdir):
        self.dbdir = dbdir
        self.live = {}
        self.log_entries = 0
        self.segments = []

    def open(self):
        os.makedirs(self.dbdir, exist_ok=True)
        names = []
        for name in os.listdir(self.dbdir):
            num = segment_number(name)
            if num is not None:
                names.append((num, name))
        names.sort()
        self.segments = [name for _, name in names]
        for name in self.segments:
            self._replay_file(os.path.join(self.dbdir, name))

    def _replay_file(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise StoreError(f"corrupt log record in {path}:{line_no}: {exc}")
                self._apply_record(record)
                self.log_entries += 1

    def _apply_record(self, record):
        op = record.get("op")
        key = record.get("key")
        if not isinstance(key, str):
            raise StoreError("corrupt log record: key must be a string")
        if op == "put":
            value = record.get("value")
            if not isinstance(value, str):
                raise StoreError("corrupt log record: value must be a string")
            self.live[key] = value
        elif op == "del":
            self.live.pop(key, None)
        else:
            raise StoreError("corrupt log record: unknown operation")

    def append_put(self, key, value):
        self._append({"op": "put", "key": key, "value": value})
        self.live[key] = value
        self.log_entries += 1

    def append_delete(self, key):
        self._append({"op": "del", "key": key})
        self.live.pop(key, None)
        self.log_entries += 1

    def _append(self, record):
        data = (compact_json(record) + "\n").encode("utf-8")
        path = self._active_path_for(len(data))
        with open(path, "ab") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())

    def _active_path_for(self, pending_bytes):
        max_bytes = get_max_segment_bytes()
        if not self.segments:
            name = self._segment_name(1)
            self.segments.append(name)
            return os.path.join(self.dbdir, name)

        current = self.segments[-1]
        current_path = os.path.join(self.dbdir, current)
        try:
            current_size = os.path.getsize(current_path)
        except FileNotFoundError:
            current_size = 0

        if current_size > 0 and current_size + pending_bytes > max_bytes:
            next_num = segment_number(current) + 1
            current = self._segment_name(next_num)
            self.segments.append(current)
        return os.path.join(self.dbdir, current)

    def compact(self):
        records = [
            {"op": "put", "key": key, "value": self.live[key]}
            for key in sorted(self.live)
        ]
        fd, tmp_path = tempfile.mkstemp(
            prefix=".compact-", suffix=".tmp", dir=self.dbdir, text=False
        )
        try:
            with os.fdopen(fd, "wb") as fh:
                for record in records:
                    fh.write((compact_json(record) + "\n").encode("utf-8"))
                fh.flush()
                os.fsync(fh.fileno())

            final_name = self._segment_name(1)
            final_path = os.path.join(self.dbdir, final_name)
            os.replace(tmp_path, final_path)

            for name in list(self.segments):
                if name != final_name:
                    path = os.path.join(self.dbdir, name)
                    try:
                        os.remove(path)
                    except FileNotFoundError:
                        pass
            self.segments = [final_name]
            self.log_entries = len(records)
            fsync_dir(self.dbdir)
        except Exception:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _segment_name(num):
        return f"{SEGMENT_PREFIX}{num:020d}{SEGMENT_SUFFIX}"


def fsync_dir(path):
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def get_max_segment_bytes():
    raw = os.environ.get("KVMINI_MAX_SEGMENT_BYTES")
    if raw is None:
        return DEFAULT_MAX_SEGMENT_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_SEGMENT_BYTES
    return max(1, value)


def usage_error(message):
    raise StoreError(message)


def require_args(command, args, count=None, minimum=None):
    if count is not None and len(args) != count:
        usage_error(f"{command} expects {count} argument(s)")
    if minimum is not None and len(args) < minimum:
        usage_error(f"{command} expects at least {minimum} argument(s)")


def run(argv):
    if len(argv) < 3:
        usage_error("usage: python3 kvmini.py DBDIR COMMAND [ARGS...]")

    dbdir = argv[1]
    command = argv[2]
    args = argv[3:]
    store = KVStore(dbdir)
    store.open()

    if command == "put":
        require_args(command, args, count=2)
        store.append_put(args[0], args[1])
        print("ok")
    elif command == "update":
        require_args(command, args, count=2)
        if args[0] not in store.live:
            raise StoreError(f"key not found: {args[0]}")
        store.append_put(args[0], args[1])
        print("ok")
    elif command == "get":
        require_args(command, args, count=1)
        if args[0] not in store.live:
            raise StoreError(f"key not found: {args[0]}")
        print(store.live[args[0]])
    elif command == "mget":
        require_args(command, args, minimum=1)
        result = {key: store.live[key] for key in args if key in store.live}
        print(compact_json(result))
    elif command == "delete":
        require_args(command, args, count=1)
        if args[0] not in store.live:
            raise StoreError(f"key not found: {args[0]}")
        store.append_delete(args[0])
        print("ok")
    elif command == "keys":
        require_args(command, args, count=0)
        print(compact_json(sorted(store.live)))
    elif command == "count":
        require_args(command, args, count=0)
        print(len(store.live))
    elif command == "list":
        require_args(command, args, count=0)
        print(compact_json({key: store.live[key] for key in sorted(store.live)}))
    elif command == "stats":
        require_args(command, args, count=0)
        print(compact_json({"live_keys": len(store.live), "log_entries": store.log_entries}))
    elif command == "compact":
        require_args(command, args, count=0)
        store.compact()
        print("ok")
    else:
        usage_error(f"unknown command: {command}")


def main():
    try:
        run(sys.argv)
    except StoreError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

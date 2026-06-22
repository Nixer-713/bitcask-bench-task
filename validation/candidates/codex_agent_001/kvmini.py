#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path


SEGMENT_RE = re.compile(r"^segment-(\d{10})-(\d{10})\.log$")
DEFAULT_MAX_SEGMENT_BYTES = 1024 * 1024


class StoreError(Exception):
    pass


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_threshold():
    raw = os.environ.get("KVMINI_MAX_SEGMENT_BYTES")
    if raw is None:
        return DEFAULT_MAX_SEGMENT_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_SEGMENT_BYTES
    return value if value > 0 else DEFAULT_MAX_SEGMENT_BYTES


def fsync_dir(path):
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class KVStore:
    def __init__(self, dbdir):
        self.dbdir = Path(dbdir)
        self.max_segment_bytes = parse_threshold()
        self.dbdir.mkdir(parents=True, exist_ok=True)
        self.generation = self._load_generation()
        self.state = {}
        self.log_entries = 0
        self._replay()

    def _load_generation(self):
        current = self.dbdir / "CURRENT"
        if current.exists():
            text = current.read_text(encoding="utf-8").strip()
            try:
                value = int(text)
            except ValueError as exc:
                raise StoreError("invalid CURRENT metadata") from exc
            if value <= 0:
                raise StoreError("invalid CURRENT metadata")
            return value

        generations = [gen for gen, _idx, _path in self._all_segments()]
        return max(generations) if generations else 1

    def _all_segments(self):
        segments = []
        if not self.dbdir.exists():
            return segments
        for path in self.dbdir.iterdir():
            match = SEGMENT_RE.match(path.name)
            if match:
                segments.append((int(match.group(1)), int(match.group(2)), path))
        return sorted(segments)

    def _segments(self):
        return [
            (idx, path)
            for gen, idx, path in self._all_segments()
            if gen == self.generation
        ]

    def _replay(self):
        for _idx, path in self._segments():
            with path.open("rb") as handle:
                for line_no, raw_line in enumerate(handle, start=1):
                    line = raw_line.rstrip(b"\n")
                    if not line:
                        continue
                    try:
                        record = json.loads(line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise StoreError(f"corrupt record in {path.name}:{line_no}") from exc
                    self._apply_record(record, path.name, line_no)
                    self.log_entries += 1

    def _apply_record(self, record, filename, line_no):
        if not isinstance(record, dict):
            raise StoreError(f"corrupt record in {filename}:{line_no}")
        op = record.get("op")
        key = record.get("key")
        if not isinstance(key, str):
            raise StoreError(f"corrupt record in {filename}:{line_no}")
        if op == "put":
            value = record.get("value")
            if not isinstance(value, str):
                raise StoreError(f"corrupt record in {filename}:{line_no}")
            self.state[key] = value
        elif op == "del":
            self.state.pop(key, None)
        else:
            raise StoreError(f"corrupt record in {filename}:{line_no}")

    def _active_segment(self, record_size):
        segments = self._segments()
        if not segments:
            return self.dbdir / f"segment-{self.generation:010d}-0000000001.log"

        idx, path = segments[-1]
        try:
            current_size = path.stat().st_size
        except FileNotFoundError:
            current_size = 0
        if current_size > 0 and current_size + record_size > self.max_segment_bytes:
            idx += 1
            return self.dbdir / f"segment-{self.generation:010d}-{idx:010d}.log"
        return path

    def append(self, record):
        data = compact_json(record).encode("utf-8") + b"\n"
        path = self._active_segment(len(data))
        with path.open("ab") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        fsync_dir(str(self.dbdir))
        self.log_entries += 1

    def put(self, key, value):
        self.append({"op": "put", "key": key, "value": value})
        self.state[key] = value

    def update(self, key, value):
        if key not in self.state:
            raise StoreError(f"key not found: {key}")
        self.append({"op": "put", "key": key, "value": value})
        self.state[key] = value

    def get(self, key):
        if key not in self.state:
            raise StoreError(f"key not found: {key}")
        return self.state[key]

    def mget(self, keys):
        result = {}
        for key in keys:
            if key in self.state:
                result[key] = self.state[key]
        return result

    def delete(self, key):
        if key not in self.state:
            raise StoreError(f"key not found: {key}")
        self.append({"op": "del", "key": key})
        del self.state[key]

    def keys(self):
        return sorted(self.state)

    def live_map(self):
        return {key: self.state[key] for key in sorted(self.state)}

    def stats(self):
        return {"live_keys": len(self.state), "log_entries": self.log_entries}

    def compact(self):
        all_generations = [gen for gen, _idx, _path in self._all_segments()]
        new_generation = max(all_generations + [self.generation]) + 1
        tmp_path = self.dbdir / f".compact-{os.getpid()}.tmp"
        new_path = self.dbdir / f"segment-{new_generation:010d}-0000000001.log"

        try:
            with tmp_path.open("wb") as handle:
                for key in sorted(self.state):
                    record = {"op": "put", "key": key, "value": self.state[key]}
                    handle.write(compact_json(record).encode("utf-8") + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, new_path)
            fsync_dir(str(self.dbdir))

            current_tmp = self.dbdir / f".CURRENT-{os.getpid()}.tmp"
            with current_tmp.open("w", encoding="utf-8") as handle:
                handle.write(f"{new_generation}\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(current_tmp, self.dbdir / "CURRENT")
            fsync_dir(str(self.dbdir))

            for gen, _idx, path in self._all_segments():
                if gen != new_generation:
                    try:
                        path.unlink()
                    except FileNotFoundError:
                        pass
            fsync_dir(str(self.dbdir))
        finally:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass

        self.generation = new_generation
        self.log_entries = len(self.state)


def usage():
    return "usage: python3 kvmini.py DBDIR COMMAND [ARGS...]"


def validate_args(argv):
    if len(argv) < 3:
        raise StoreError(usage())
    command = argv[2]
    args = argv[3:]
    arity = {
        "put": 2,
        "update": 2,
        "get": 1,
        "delete": 1,
        "keys": 0,
        "count": 0,
        "list": 0,
        "stats": 0,
        "compact": 0,
    }
    if command == "mget":
        if len(args) < 1:
            raise StoreError(usage())
    elif command in arity:
        if len(args) != arity[command]:
            raise StoreError(usage())
    else:
        raise StoreError(f"unknown command: {command}")
    return argv[1], command, args


def run(argv):
    dbdir, command, args = validate_args(argv)
    store = KVStore(dbdir)

    if command == "put":
        store.put(args[0], args[1])
    elif command == "update":
        store.update(args[0], args[1])
    elif command == "get":
        print(store.get(args[0]))
    elif command == "mget":
        print(compact_json(store.mget(args)))
    elif command == "delete":
        store.delete(args[0])
    elif command == "keys":
        print(compact_json(store.keys()))
    elif command == "count":
        print(len(store.state))
    elif command == "list":
        print(compact_json(store.live_map()))
    elif command == "stats":
        print(compact_json(store.stats()))
    elif command == "compact":
        store.compact()
    return 0


def main():
    try:
        return run(sys.argv)
    except StoreError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

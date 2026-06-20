#!/usr/bin/env python3.11
"""
kvmini.py -- a compact, disk-backed, log-structured key/value store CLI.

Reference solution for the `bitcask-realrepo-001` unit/system benchmark packet.

Model:
  * The store lives in a DIRECTORY (DBDIR). Each invocation opens the store,
    reloads its state from the append-only segment files on disk, performs one
    command, persists, and exits. Durability across separate process
    invocations is therefore a first-class property.
  * Writes (`put`, `update`, `delete`) only ever APPEND to the active segment.
    When the active segment exceeds the size threshold it is rolled over and a
    new active segment is started. Old segments are immutable.
  * An in-memory map of key -> latest record is rebuilt on every open by
    replaying segments in write order. The latest record for a key wins;
    a tombstone record marks the key deleted.
  * `compact` (merge) rewrites the log so that only the latest live value of
    each key remains and tombstones are discarded; observable semantics are
    unchanged.

Record format (one JSON object per line inside a *.seg file):
    {"k": <key str>, "v": <value str or null>, "d": <0|1 tombstone>}
Records are ordered by (segment id, line number) == write order.

Usage:
    py -3.11 kvmini.py DBDIR COMMAND [ARGS...]
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

MAX_SEGMENT_BYTES_DEFAULT = 4096
SEG_SUFFIX = ".seg"


def _max_segment_bytes() -> int:
    raw = os.environ.get("KVMINI_MAX_SEGMENT_BYTES")
    if raw:
        try:
            n = int(raw)
            if n > 0:
                return n
        except ValueError:
            pass
    return MAX_SEGMENT_BYTES_DEFAULT


def _die(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    sys.stderr.write(msg.rstrip("\n") + "\n")
    sys.exit(code)


def _dump(obj) -> str:
    """Compact, deterministic JSON for stdout."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


class Store:
    def __init__(self, directory: str):
        self.directory = directory
        # ordered list of live state, plus map for lookup
        self.data: "dict[str, str]" = {}
        # number of physical records currently persisted on disk
        self.log_entries = 0
        self._loaded = False

    # ---- segment helpers -------------------------------------------------
    def _segment_files(self) -> "list[str]":
        if not os.path.isdir(self.directory):
            return []
        names = [n for n in os.listdir(self.directory) if n.endswith(SEG_SUFFIX)]
        names.sort()  # zero-padded ids sort in write order
        return [os.path.join(self.directory, n) for n in names]

    def _next_segment_path(self) -> str:
        existing = [
            os.path.basename(p)[: -len(SEG_SUFFIX)] for p in self._segment_files()
        ]
        ids = [int(x) for x in existing if x.isdigit()]
        nxt = (max(ids) + 1) if ids else 1
        return os.path.join(self.directory, f"{nxt:09d}{SEG_SUFFIX}")

    def _active_segment_path(self) -> str:
        segs = self._segment_files()
        if not segs:
            return self._next_segment_path()
        last = segs[-1]
        try:
            if os.path.getsize(last) >= _max_segment_bytes():
                return self._next_segment_path()
        except OSError:
            return self._next_segment_path()
        return last

    # ---- load / persist --------------------------------------------------
    def load(self) -> None:
        self.data = {}
        self.log_entries = 0
        for path in self._segment_files():
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    self.log_entries += 1
                    key = rec["k"]
                    if rec.get("d"):
                        self.data.pop(key, None)
                    else:
                        self.data[key] = rec["v"]
        self._loaded = True

    def _append(self, key: str, value: Optional[str], tombstone: bool) -> None:
        os.makedirs(self.directory, exist_ok=True)
        rec = {"k": key, "v": value, "d": 1 if tombstone else 0}
        path = self._active_segment_path()
        line = json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        self.log_entries += 1

    # ---- public operations ----------------------------------------------
    def put(self, key: str, value: str) -> None:
        self._append(key, value, False)
        self.data[key] = value

    def update(self, key: str, value: str) -> None:
        if key not in self.data:
            _die(f"update failed: key {key!r} does not exist")
        self._append(key, value, False)
        self.data[key] = value

    def get(self, key: str) -> str:
        if key not in self.data:
            _die(f"get failed: key {key!r} does not exist")
        return self.data[key]

    def mget(self, keys: "list[str]") -> "dict[str, str]":
        return {k: self.data[k] for k in keys if k in self.data}

    def delete(self, key: str) -> None:
        if key not in self.data:
            _die(f"delete failed: key {key!r} does not exist")
        self._append(key, None, True)
        self.data.pop(key, None)

    def keys(self) -> "list[str]":
        return sorted(self.data.keys())

    def count(self) -> int:
        return len(self.data)

    def listing(self) -> "dict[str, str]":
        return dict(self.data)

    def stats(self) -> "dict[str, int]":
        return {"live_keys": len(self.data), "log_entries": self.log_entries}

    def compact(self) -> None:
        # Rewrite the whole log into fresh segments holding only live latest
        # values, in key order, dropping tombstones and superseded records.
        live = sorted(self.data.items())
        old = self._segment_files()
        os.makedirs(self.directory, exist_ok=True)
        # write compacted segments respecting the size threshold
        written = 0
        seg_idx = 0
        cur_path = os.path.join(self.directory, f"c{seg_idx:08d}{SEG_SUFFIX}")
        fh = open(cur_path, "w", encoding="utf-8")
        new_paths = [cur_path]
        try:
            for k, v in live:
                if fh.tell() >= _max_segment_bytes() and written > 0:
                    fh.flush()
                    os.fsync(fh.fileno())
                    fh.close()
                    seg_idx += 1
                    cur_path = os.path.join(
                        self.directory, f"c{seg_idx:08d}{SEG_SUFFIX}"
                    )
                    fh = open(cur_path, "w", encoding="utf-8")
                    new_paths.append(cur_path)
                rec = {"k": k, "v": v, "d": 0}
                fh.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n")
                written += 1
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fh.close()
        # remove the pre-compaction segments
        new_set = set(new_paths)
        for p in old:
            if p not in new_set:
                try:
                    os.remove(p)
                except OSError:
                    pass
        # rename compacted segments into the canonical numeric namespace so
        # that future appends continue cleanly after them
        for i, p in enumerate(sorted(new_paths), start=1):
            dest = os.path.join(self.directory, f"{i:09d}{SEG_SUFFIX}")
            if os.path.abspath(p) != os.path.abspath(dest):
                os.replace(p, dest)
        self.log_entries = written


def main(argv: "list[str]") -> int:
    if len(argv) < 2:
        _die("usage: kvmini.py DBDIR COMMAND [ARGS...]", 2)
    dbdir = argv[0]
    command = argv[1]
    rest = argv[2:]

    store = Store(dbdir)
    store.load()

    if command == "put":
        if len(rest) != 2:
            _die("usage: put KEY VALUE", 2)
        store.put(rest[0], rest[1])
        print("OK")
    elif command == "update":
        if len(rest) != 2:
            _die("usage: update KEY VALUE", 2)
        store.update(rest[0], rest[1])
        print("OK")
    elif command == "get":
        if len(rest) != 1:
            _die("usage: get KEY", 2)
        sys.stdout.write(store.get(rest[0]) + "\n")
    elif command == "mget":
        if len(rest) < 1:
            _die("usage: mget KEY [KEY...]", 2)
        print(_dump(store.mget(rest)))
    elif command == "delete":
        if len(rest) != 1:
            _die("usage: delete KEY", 2)
        store.delete(rest[0])
        print("OK")
    elif command == "keys":
        if rest:
            _die("usage: keys", 2)
        print(_dump(store.keys()))
    elif command == "count":
        if rest:
            _die("usage: count", 2)
        print(store.count())
    elif command == "list":
        if rest:
            _die("usage: list", 2)
        print(_dump(store.listing()))
    elif command == "stats":
        if rest:
            _die("usage: stats", 2)
        print(_dump(store.stats()))
    elif command == "compact":
        if rest:
            _die("usage: compact", 2)
        store.compact()
        print("OK")
    else:
        _die(f"unknown command: {command}", 2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

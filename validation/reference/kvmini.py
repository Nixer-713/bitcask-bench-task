#!/usr/bin/env python3
"""Reference implementation for the mini-bitcask validation branch."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_MAX_SEGMENT_BYTES = 1024 * 1024


class UserError(Exception):
    pass


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def segment_limit() -> int:
    raw = os.environ.get("KVMINI_MAX_SEGMENT_BYTES")
    if raw is None:
        return DEFAULT_MAX_SEGMENT_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_SEGMENT_BYTES
    return value if value > 0 else DEFAULT_MAX_SEGMENT_BYTES


def segment_path(dbdir: Path, index: int) -> Path:
    return dbdir / f"{index:020d}.jsonl"


class Store:
    def __init__(self, dbdir: Path) -> None:
        self.dbdir = dbdir
        self.limit = segment_limit()
        self.live: dict[str, str] = {}
        self.log_entries = 0
        self.segments: list[Path] = []
        self.load()

    def load(self) -> None:
        if not self.dbdir.exists():
            return
        if not self.dbdir.is_dir():
            raise UserError(f"{self.dbdir} is not a directory")
        self.segments = sorted(self.dbdir.glob("*.jsonl"))
        for path in self.segments:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    raw = line.strip()
                    if not raw:
                        continue
                    record = json.loads(raw)
                    key = record.get("key")
                    if not isinstance(key, str):
                        raise UserError("corrupt record")
                    op = record.get("op")
                    if op == "put":
                        value = record.get("value")
                        if not isinstance(value, str):
                            raise UserError("corrupt record")
                        self.live[key] = value
                    elif op == "delete":
                        self.live.pop(key, None)
                    else:
                        raise UserError("corrupt record")
                    self.log_entries += 1

    def ensure_dir(self) -> None:
        self.dbdir.mkdir(parents=True, exist_ok=True)

    def active_segment(self, payload_size: int) -> Path:
        self.ensure_dir()
        if not self.segments:
            path = segment_path(self.dbdir, 1)
            self.segments.append(path)
            return path
        path = self.segments[-1]
        current_size = path.stat().st_size if path.exists() else 0
        if current_size > 0 and current_size + payload_size > self.limit:
            path = segment_path(self.dbdir, len(self.segments) + 1)
            self.segments.append(path)
        return path

    def append(self, record: dict[str, Any]) -> None:
        payload = (compact_json(record) + "\n").encode("utf-8")
        path = self.active_segment(len(payload))
        with path.open("ab") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        self.log_entries += 1

    def put(self, key: str, value: str) -> None:
        self.append({"op": "put", "key": key, "value": value})
        self.live[key] = value

    def update(self, key: str, value: str) -> None:
        if key not in self.live:
            raise UserError(f"missing key: {key}")
        self.put(key, value)

    def delete(self, key: str) -> None:
        if key not in self.live:
            raise UserError(f"missing key: {key}")
        self.append({"op": "delete", "key": key})
        del self.live[key]

    def compact(self) -> None:
        self.ensure_dir()
        tmp = self.dbdir / ".compact.tmp"
        with tmp.open("wb") as handle:
            for key in sorted(self.live):
                payload = compact_json({"op": "put", "key": key, "value": self.live[key]}) + "\n"
                handle.write(payload.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        for path in self.segments:
            path.unlink(missing_ok=True)
        if self.live:
            final = segment_path(self.dbdir, 1)
            os.replace(tmp, final)
            self.segments = [final]
        else:
            tmp.unlink(missing_ok=True)
            self.segments = []
        self.log_entries = len(self.live)


def require_count(command: str, args: list[str], count: int) -> None:
    if len(args) != count:
        raise UserError(f"{command} expects {count} argument(s)")


def run(argv: list[str]) -> int:
    if len(argv) < 3:
        raise UserError("usage: kvmini.py DBDIR COMMAND [ARGS...]")
    dbdir = Path(argv[1])
    command = argv[2]
    args = argv[3:]

    if command == "put":
        require_count(command, args, 2)
        Store(dbdir).put(args[0], args[1])
    elif command == "update":
        require_count(command, args, 2)
        Store(dbdir).update(args[0], args[1])
    elif command == "get":
        require_count(command, args, 1)
        store = Store(dbdir)
        if args[0] not in store.live:
            raise UserError(f"missing key: {args[0]}")
        print(store.live[args[0]])
    elif command == "mget":
        if not args:
            raise UserError("mget expects at least one key")
        store = Store(dbdir)
        print(compact_json({key: store.live[key] for key in args if key in store.live}))
    elif command == "delete":
        require_count(command, args, 1)
        Store(dbdir).delete(args[0])
    elif command == "keys":
        require_count(command, args, 0)
        print(compact_json(sorted(Store(dbdir).live)))
    elif command == "count":
        require_count(command, args, 0)
        print(len(Store(dbdir).live))
    elif command == "list":
        require_count(command, args, 0)
        store = Store(dbdir)
        print(compact_json({key: store.live[key] for key in sorted(store.live)}))
    elif command == "stats":
        require_count(command, args, 0)
        store = Store(dbdir)
        print(compact_json({"live_keys": len(store.live), "log_entries": store.log_entries}))
    elif command == "compact":
        require_count(command, args, 0)
        Store(dbdir).compact()
    else:
        raise UserError(f"unknown command: {command}")
    return 0


def main() -> int:
    try:
        return run(sys.argv)
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

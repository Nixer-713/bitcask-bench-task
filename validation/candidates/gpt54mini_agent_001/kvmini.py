#!/usr/bin/env python3
"""MiniBitcask-style key/value store for the validation benchmark.

Usage:
    python3 kvmini.py DBDIR COMMAND [ARGS...]
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


CURRENT_MARKER = "CURRENT"
SEGMENT_RE = re.compile(r"^gen-(\d+)-seg-(\d+)\.log$")
DEFAULT_MAX_SEGMENT_BYTES = 1024 * 1024


def eprint(message: str) -> None:
    sys.stderr.write(message.rstrip("\n") + "\n")


def fail(message: str, code: int = 1) -> "NoReturn":
    eprint(message)
    raise SystemExit(code)


def parse_threshold() -> int:
    raw = os.getenv("KVMINI_MAX_SEGMENT_BYTES")
    if raw is None or raw == "":
        return DEFAULT_MAX_SEGMENT_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_SEGMENT_BYTES
    return value if value > 0 else DEFAULT_MAX_SEGMENT_BYTES


def segment_name(gen: int, seg: int) -> str:
    return f"gen-{gen:06d}-seg-{seg:06d}.log"


def segment_path(dbdir: Path, gen: int, seg: int) -> Path:
    return dbdir / segment_name(gen, seg)


def current_marker_path(dbdir: Path) -> Path:
    return dbdir / CURRENT_MARKER


def read_current_marker(dbdir: Path) -> Optional[int]:
    path = current_marker_path(dbdir)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return None
        value = int(text)
        return value if value > 0 else None
    except (OSError, ValueError):
        return None


def write_current_marker(dbdir: Path, gen: int) -> None:
    dbdir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".current.", dir=str(dbdir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{gen}\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, current_marker_path(dbdir))
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


def scan_generations(dbdir: Path) -> Dict[int, List[Tuple[int, Path]]]:
    generations: Dict[int, List[Tuple[int, Path]]] = {}
    if not dbdir.exists():
        return generations
    for name in os.listdir(dbdir):
        match = SEGMENT_RE.match(name)
        if not match:
            continue
        gen = int(match.group(1))
        seg = int(match.group(2))
        generations.setdefault(gen, []).append((seg, dbdir / name))
    for segs in generations.values():
        segs.sort(key=lambda item: item[0])
    return generations


def choose_active_generation(dbdir: Path) -> int:
    marker = read_current_marker(dbdir)
    generations = scan_generations(dbdir)
    if marker is not None and marker in generations:
        return marker
    if generations:
        return max(generations)
    return marker if marker is not None else 1


@dataclass
class Store:
    dbdir: Path
    max_segment_bytes: int
    current_gen: int
    live: Dict[str, str]
    segment_index: int
    segment_size: int
    log_entries: int

    @classmethod
    def open(cls, dbdir: Path, create: bool) -> "Store":
        if create:
            dbdir.mkdir(parents=True, exist_ok=True)
        generations = scan_generations(dbdir)
        current_gen = choose_active_generation(dbdir)
        live: Dict[str, str] = {}
        log_entries = 0

        current_segments = generations.get(current_gen, [])
        for _, path in current_segments:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    text = line.rstrip("\n")
                    if not text:
                        continue
                    try:
                        record = json.loads(text)
                    except json.JSONDecodeError as exc:
                        fail(f"corrupt log record in {path.name}: {exc.msg}")
                    op = record.get("op")
                    key = record.get("key")
                    if not isinstance(key, str) or not isinstance(op, str):
                        fail(f"corrupt log record in {path.name}")
                    if op == "put" or op == "update":
                        value = record.get("value")
                        if not isinstance(value, str):
                            fail(f"corrupt log record in {path.name}")
                        live[key] = value
                    elif op == "delete":
                        live.pop(key, None)
                    else:
                        fail(f"corrupt log record in {path.name}")
                    log_entries += 1

        if current_segments:
            segment_index, last_path = current_segments[-1]
            segment_size = last_path.stat().st_size
        else:
            segment_index = 0
            segment_size = 0

        return cls(
            dbdir=dbdir,
            max_segment_bytes=parse_threshold(),
            current_gen=current_gen,
            live=live,
            segment_index=segment_index,
            segment_size=segment_size,
            log_entries=log_entries,
        )

    def ensure_marker(self) -> None:
        existing = read_current_marker(self.dbdir)
        if existing == self.current_gen:
            return
        write_current_marker(self.dbdir, self.current_gen)

    def _roll_segment_if_needed(self, encoded_size: int) -> None:
        if self.segment_index == 0:
            self.segment_index = 1
            self.segment_size = 0
            return
        if self.segment_size > 0 and self.segment_size + encoded_size > self.max_segment_bytes:
            self.segment_index += 1
            self.segment_size = 0

    def append_record(self, record: dict) -> None:
        self.ensure_marker()
        payload = json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
        encoded = payload.encode("utf-8")
        self._roll_segment_if_needed(len(encoded))
        path = segment_path(self.dbdir, self.current_gen, self.segment_index or 1)
        self.dbdir.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        self.segment_index = self.segment_index or 1
        self.segment_size += len(encoded)
        self.log_entries += 1

    def put(self, key: str, value: str) -> None:
        self.append_record({"op": "put", "key": key, "value": value})
        self.live[key] = value

    def update(self, key: str, value: str) -> None:
        if key not in self.live:
            fail(f"update: missing key {key!r}")
        self.append_record({"op": "update", "key": key, "value": value})
        self.live[key] = value

    def delete(self, key: str) -> None:
        if key not in self.live:
            fail(f"delete: missing key {key!r}")
        self.append_record({"op": "delete", "key": key})
        self.live.pop(key, None)

    def compact(self) -> None:
        # Compact into a fresh generation so old generations can stay ignored
        # even if the process crashes before cleanup.
        new_gen = max(self.current_gen, self._max_known_generation()) + 1
        writer = _GenerationWriter(self.dbdir, new_gen, self.max_segment_bytes)
        writer.write_snapshot(self.live)
        writer.finish()
        self.current_gen = new_gen
        self.segment_index = writer.segment_index
        self.segment_size = writer.segment_size
        self.log_entries = len(self.live)
        self.ensure_marker()

    def _max_known_generation(self) -> int:
        generations = scan_generations(self.dbdir)
        return max(generations) if generations else self.current_gen


class _GenerationWriter:
    def __init__(self, dbdir: Path, gen: int, max_segment_bytes: int) -> None:
        self.dbdir = dbdir
        self.gen = gen
        self.max_segment_bytes = max_segment_bytes
        self.segment_index = 0
        self.segment_size = 0

    def _roll(self, encoded_size: int) -> None:
        if self.segment_index == 0:
            self.segment_index = 1
            self.segment_size = 0
            return
        if self.segment_size > 0 and self.segment_size + encoded_size > self.max_segment_bytes:
            self.segment_index += 1
            self.segment_size = 0

    def _append(self, record: dict) -> None:
        payload = json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
        encoded = payload.encode("utf-8")
        self._roll(len(encoded))
        path = segment_path(self.dbdir, self.gen, self.segment_index or 1)
        self.dbdir.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        self.segment_index = self.segment_index or 1
        self.segment_size += len(encoded)

    def write_snapshot(self, live: Dict[str, str]) -> None:
        if not live:
            # Keep a concrete empty active file so the generation is explicit.
            path = segment_path(self.dbdir, self.gen, 1)
            self.dbdir.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n"):
                pass
            self.segment_index = 1
            self.segment_size = path.stat().st_size
            return
        for key in sorted(live):
            self._append({"op": "put", "key": key, "value": live[key]})

    def finish(self) -> None:
        write_current_marker(self.dbdir, self.gen)


def dump_json(value: object) -> None:
    sys.stdout.write(json.dumps(value, separators=(",", ":"), ensure_ascii=False))
    sys.stdout.write("\n")


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        fail("usage: kvmini.py DBDIR COMMAND [ARGS...]")

    dbdir = Path(argv[1])
    command = argv[2]
    args = argv[3:]

    if command not in {"put", "update", "get", "mget", "delete", "keys", "count", "list", "stats", "compact"}:
        fail(f"unknown command: {command}")

    if command == "put":
        if len(args) != 2:
            fail("put expects KEY VALUE")
        store = Store.open(dbdir, create=True)
        store.put(args[0], args[1])
        return 0

    if command == "update":
        if len(args) != 2:
            fail("update expects KEY VALUE")
        store = Store.open(dbdir, create=True)
        store.update(args[0], args[1])
        return 0

    if command == "get":
        if len(args) != 1:
            fail("get expects KEY")
        store = Store.open(dbdir, create=False)
        key = args[0]
        if key not in store.live:
            fail(f"get: missing key {key!r}")
        sys.stdout.write(store.live[key])
        sys.stdout.write("\n")
        return 0

    if command == "mget":
        if len(args) < 1:
            fail("mget expects at least one KEY")
        store = Store.open(dbdir, create=False)
        result = {key: store.live[key] for key in args if key in store.live}
        dump_json(result)
        return 0

    if command == "delete":
        if len(args) != 1:
            fail("delete expects KEY")
        store = Store.open(dbdir, create=True)
        store.delete(args[0])
        return 0

    if command == "keys":
        if args:
            fail("keys expects no arguments")
        store = Store.open(dbdir, create=False)
        dump_json(sorted(store.live))
        return 0

    if command == "count":
        if args:
            fail("count expects no arguments")
        store = Store.open(dbdir, create=False)
        sys.stdout.write(f"{len(store.live)}\n")
        return 0

    if command == "list":
        if args:
            fail("list expects no arguments")
        store = Store.open(dbdir, create=False)
        dump_json({key: store.live[key] for key in sorted(store.live)})
        return 0

    if command == "stats":
        if args:
            fail("stats expects no arguments")
        store = Store.open(dbdir, create=False)
        dump_json({"live_keys": len(store.live), "log_entries": store.log_entries})
        return 0

    if command == "compact":
        if args:
            fail("compact expects no arguments")
        store = Store.open(dbdir, create=True)
        store.compact()
        return 0

    fail(f"unhandled command: {command}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

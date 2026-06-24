#!/usr/bin/env python3
import argparse
import calendar
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


STATUS_TO_BOX = {
    "open": "[ ]",
    "done": "[x]",
    "ongoing": "[@]",
    "obsolete": "[~]",
    "question": "[?]",
}
BOX_TO_STATUS = {v: k for k, v in STATUS_TO_BOX.items()}
DATE_RE = re.compile(r"->\s+(\d{4}(?:[-/](?:\d{2}(?:[-/]\d{2})?|W\d{2})|-Q[1-4])?)")
TAG_RE = re.compile(r"#([\w-]+)(?:=(\"[^\"]*\"|'[^']*'|[^\s#]+))?", re.UNICODE)


@dataclass
class Task:
    id: int
    file: str
    line: int
    line_index: int
    end_index: int
    status: str
    priority: int
    body: str
    continuations: list[str]
    due: str | None
    tags: dict[str, str | None]

    @property
    def description(self) -> str:
        parts = [self.body] + self.continuations
        return "\n".join(parts)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "file": self.file,
            "line": self.line,
            "status": self.status,
            "description": self.description,
            "priority": self.priority,
            "due": self.due,
            "tags": self.tags,
        }


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def emit(value) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def require_xit(path: str) -> None:
    if not path.endswith(".xit"):
        fail("unsupported file extension")


def read_lines(path: str, must_exist: bool = True) -> list[str]:
    require_xit(path)
    p = Path(path)
    if not p.exists():
        if must_exist:
            fail(f"missing file: {path}")
        return []
    return p.read_text(encoding="utf-8").splitlines(keepends=True)


def write_lines(path: str, lines: list[str]) -> None:
    require_xit(path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(lines), encoding="utf-8")


def split_task_text(text: str) -> tuple[int, str]:
    text = text.rstrip("\n")
    if not text:
        return 0, ""
    first, sep, rest = text.partition(" ")
    if is_priority_token(first):
        return first.count("!"), rest if sep else ""
    return 0, text


def is_priority_token(token: str) -> bool:
    if not token:
        return False
    return (
        re.fullmatch(r"!+", token) is not None
        or re.fullmatch(r"\.+!+", token) is not None
        or re.fullmatch(r"!+\.+", token) is not None
    )


def normalize_date(value: str) -> str:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value) or re.fullmatch(
        r"(\d{4})/(\d{2})/(\d{2})", value
    )
    if m:
        y, mo, d = map(int, m.groups())
        return date(y, mo, d).isoformat()
    m = re.fullmatch(r"(\d{4})-(\d{2})", value) or re.fullmatch(r"(\d{4})/(\d{2})", value)
    if m:
        y, mo = map(int, m.groups())
        return date(y, mo, calendar.monthrange(y, mo)[1]).isoformat()
    m = re.fullmatch(r"(\d{4})", value)
    if m:
        return f"{int(m.group(1)):04d}-12-31"
    m = re.fullmatch(r"(\d{4})[-/](W\d{2})", value)
    if m:
        y = int(m.group(1))
        week = int(m.group(2)[1:])
        return date.fromisocalendar(y, week, 7).isoformat()
    m = re.fullmatch(r"(\d{4})-Q([1-4])", value)
    if m:
        y = int(m.group(1))
        q = int(m.group(2))
        month = q * 3
        return date(y, month, calendar.monthrange(y, month)[1]).isoformat()
    raise ValueError(value)


def extract_due(text: str) -> str | None:
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        return normalize_date(m.group(1))
    except ValueError:
        return None


def parse_tags(text: str) -> dict[str, str | None]:
    tags: dict[str, str | None] = {}
    for m in TAG_RE.finditer(text):
        raw = m.group(2)
        if raw is None:
            tags[m.group(1)] = None
        elif len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
            tags[m.group(1)] = raw[1:-1]
        else:
            tags[m.group(1)] = raw
    return tags


def parse_files(paths: list[str]) -> tuple[list[Task], dict[str, list[str]]]:
    tasks: list[Task] = []
    files: dict[str, list[str]] = {}
    next_id = 1
    for path in paths:
        lines = read_lines(path, must_exist=True)
        files[path] = lines
        i = 0
        while i < len(lines):
            raw = lines[i].rstrip("\n")
            if len(raw) >= 3 and raw[:3] in BOX_TO_STATUS and (len(raw) == 3 or raw[3] == " "):
                text = raw[4:] if len(raw) > 3 else ""
                priority, body = split_task_text(text)
                cont: list[str] = []
                j = i + 1
                while j < len(lines) and lines[j].startswith("    "):
                    cont.append(lines[j][4:].rstrip("\n"))
                    j += 1
                task = Task(
                    id=next_id,
                    file=path,
                    line=i + 1,
                    line_index=i,
                    end_index=j,
                    status=BOX_TO_STATUS[raw[:3]],
                    priority=priority,
                    body=body,
                    continuations=cont,
                    due=extract_due(body),
                    tags=parse_tags(body),
                )
                tasks.append(task)
                next_id += 1
                i = j
            else:
                i += 1
    return tasks, files


def parse_one(path: str) -> tuple[list[Task], list[str]]:
    tasks, files = parse_files([path])
    return tasks, files[path]


def task_by_id(path: str, task_id: int) -> tuple[Task, list[Task], list[str]]:
    tasks, lines = parse_one(path)
    for task in tasks:
        if task.id == task_id:
            return task, tasks, lines
    fail("task ID not found")


def strip_due_and_tags(body: str) -> str:
    body = DATE_RE.sub("", body)
    body = TAG_RE.sub("", body)
    return " ".join(body.split())


def parse_tag_arg(value: str) -> tuple[str, str | None]:
    if value.startswith("#"):
        fail("tag argument must not start with #")
    name, sep, raw = value.partition("=")
    if not re.fullmatch(r"[\w-]+", name, re.UNICODE):
        fail("invalid tag")
    if not sep:
        return name, None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return name, raw[1:-1]
    return name, raw


def format_tag(name: str, value: str | None) -> str:
    return f"#{name}" if value is None else f"#{name}={value}"


def build_line(status: str, priority: int, text: str, due: str | None, tags: list[tuple[str, str | None]]) -> str:
    if status not in STATUS_TO_BOX:
        fail("unsupported status")
    parts = [STATUS_TO_BOX[status]]
    if priority:
        parts.append("!" * priority)
    clean = text.strip()
    if clean:
        parts.append(clean)
    if due:
        parts.extend(["->", due])
    parts.extend(format_tag(k, v) for k, v in tags)
    return " ".join(parts) + "\n"


def replace_first_line(lines: list[str], task: Task, new_line: str) -> list[str]:
    updated = list(lines)
    updated[task.line_index] = new_line
    return updated


def list_command(args) -> None:
    tasks, _ = parse_files(args.file)
    if args.status:
        if args.status not in STATUS_TO_BOX:
            fail("unsupported status")
        tasks = [t for t in tasks if t.status == args.status]
    for tag in args.tag or []:
        name, _ = parse_tag_arg(tag)
        tasks = [t for t in tasks if name in t.tags]
    if args.priority_min is not None:
        tasks = [t for t in tasks if t.priority >= args.priority_min]
    if args.due_on:
        due = checked_date(args.due_on)
        tasks = [t for t in tasks if t.due == due]
    if args.due_by:
        due = checked_date(args.due_by)
        tasks = [t for t in tasks if t.due is not None and t.due <= due]

    reverse = args.order == "desc"
    if args.sort == "id":
        tasks.sort(key=lambda t: t.id, reverse=reverse)
    elif args.sort == "priority":
        tasks.sort(key=lambda t: (-t.priority if reverse else t.priority, t.id))
    elif args.sort == "due":
        if reverse:
            tasks.sort(key=lambda t: (t.due is not None, t.due or ""), reverse=True)
        else:
            tasks.sort(key=lambda t: (t.due is None, t.due or "", t.id))
    emit([t.to_json() for t in tasks])


def stats_command(args) -> None:
    tasks, _ = parse_files(args.file)
    result = {
        "total": len(tasks),
        "by_status": {},
        "by_priority": {},
        "by_file": {},
        "with_tags": 0,
        "with_due": 0,
    }
    for task in tasks:
        result["by_status"][task.status] = result["by_status"].get(task.status, 0) + 1
        key = str(task.priority)
        result["by_priority"][key] = result["by_priority"].get(key, 0) + 1
        result["by_file"][task.file] = result["by_file"].get(task.file, 0) + 1
        if task.tags:
            result["with_tags"] += 1
        if task.due:
            result["with_due"] += 1
    emit(result)


def checked_date(value: str) -> str:
    try:
        return normalize_date(value)
    except Exception:
        fail("invalid date argument")


def add_command(args) -> None:
    require_xit(args.file)
    status = args.status or "open"
    if status not in STATUS_TO_BOX:
        fail("unsupported status")
    due = checked_date(args.due) if args.due else None
    tags = [parse_tag_arg(t) for t in (args.tag or [])]
    priority = args.priority or 0
    if priority < 0:
        fail("invalid priority")
    lines = read_lines(args.file, must_exist=False)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines.append(build_line(status, priority, args.text, due, tags))
    write_lines(args.file, lines)
    tasks, _ = parse_files([args.file])
    emit(tasks[-1].to_json())


def mark_command(args) -> None:
    if args.status not in STATUS_TO_BOX:
        fail("unsupported status")
    task, _, lines = task_by_id(args.file, int(args.id))
    old = lines[task.line_index]
    new_line = STATUS_TO_BOX[args.status] + old[3:]
    write_lines(args.file, replace_first_line(lines, task, new_line))
    tasks, _ = parse_files([args.file])
    emit(tasks[task.id - 1].to_json())


def tag_command(args) -> None:
    name, value = parse_tag_arg(args.tag_value)
    task, _, lines = task_by_id(args.file, int(args.id))
    base = strip_due_and_tags(task.body)
    tags = dict(task.tags)
    tags[name] = value
    new_line = build_line(task.status, task.priority, base, task.due, list(tags.items()))
    write_lines(args.file, replace_first_line(lines, task, new_line))
    tasks, _ = parse_files([args.file])
    emit(tasks[task.id - 1].to_json())


def untag_command(args) -> None:
    name, _ = parse_tag_arg(args.tag_value)
    task, _, lines = task_by_id(args.file, int(args.id))
    base = strip_due_and_tags(task.body)
    tags = dict(task.tags)
    tags.pop(name, None)
    new_line = build_line(task.status, task.priority, base, task.due, list(tags.items()))
    write_lines(args.file, replace_first_line(lines, task, new_line))
    tasks, _ = parse_files([args.file])
    emit(tasks[task.id - 1].to_json())


def reschedule_command(args) -> None:
    due = checked_date(args.date)
    task, _, lines = task_by_id(args.file, int(args.id))
    base = strip_due_and_tags(task.body)
    new_line = build_line(task.status, task.priority, base, due, list(task.tags.items()))
    write_lines(args.file, replace_first_line(lines, task, new_line))
    tasks, _ = parse_files([args.file])
    emit(tasks[task.id - 1].to_json())


def move_command(args) -> None:
    task, _, src_lines = task_by_id(args.src, int(args.id))
    dst_lines = read_lines(args.dst, must_exist=False)
    block = src_lines[task.line_index : task.end_index]
    new_src = src_lines[: task.line_index] + src_lines[task.end_index :]
    if dst_lines and not dst_lines[-1].endswith("\n"):
        dst_lines[-1] += "\n"
    new_dst = dst_lines + block
    write_lines(args.src, new_src)
    write_lines(args.dst, new_dst)
    tasks, _ = parse_files([args.dst])
    emit(tasks[-1].to_json())


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xitlite.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list")
    p.add_argument("--file", action="append", required=True)
    p.add_argument("--status")
    p.add_argument("--tag", action="append")
    p.add_argument("--priority-min", type=int)
    p.add_argument("--due-on")
    p.add_argument("--due-by")
    p.add_argument("--sort", choices=["id", "priority", "due"], default="id")
    p.add_argument("--order", choices=["asc", "desc"], default="asc")
    p.set_defaults(func=list_command)

    p = sub.add_parser("stats")
    p.add_argument("--file", action="append", required=True)
    p.set_defaults(func=stats_command)

    p = sub.add_parser("add")
    p.add_argument("--file", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--status")
    p.add_argument("--priority", type=int)
    p.add_argument("--due")
    p.add_argument("--tag", action="append")
    p.set_defaults(func=add_command)

    p = sub.add_parser("mark")
    p.add_argument("--file", required=True)
    p.add_argument("id")
    p.add_argument("--status", required=True)
    p.set_defaults(func=mark_command)

    p = sub.add_parser("tag")
    p.add_argument("--file", required=True)
    p.add_argument("id")
    p.add_argument("tag_value")
    p.set_defaults(func=tag_command)

    p = sub.add_parser("untag")
    p.add_argument("--file", required=True)
    p.add_argument("id")
    p.add_argument("tag_value")
    p.set_defaults(func=untag_command)

    p = sub.add_parser("reschedule")
    p.add_argument("--file", required=True)
    p.add_argument("id")
    p.add_argument("date")
    p.set_defaults(func=reschedule_command)

    p = sub.add_parser("move")
    p.add_argument("--from", dest="src", required=True)
    p.add_argument("--to", dest="dst", required=True)
    p.add_argument("id")
    p.set_defaults(func=move_command)
    return parser


def main() -> None:
    parser = make_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as exc:
        fail(str(exc) or "command failed")


if __name__ == "__main__":
    main()

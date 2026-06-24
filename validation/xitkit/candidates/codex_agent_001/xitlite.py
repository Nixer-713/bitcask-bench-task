#!/usr/bin/env python3
import argparse
import calendar
import json
import os
import re
import sys
from copy import deepcopy
from datetime import date


STATUSES = {
    "open": "[ ]",
    "done": "[x]",
    "ongoing": "[@]",
    "obsolete": "[~]",
    "question": "[?]",
}
CHECKBOX_STATUS = {v: k for k, v in STATUSES.items()}
TASK_RE = re.compile(r"^(\[ \]|\[x\]|\[@\]|\[~\]|\[\?\])(?:$| (.*)$)")
PRIORITY_RE = re.compile(r"^(?:(!+)\.*|(\.*)(!+))$")
TAG_RE = re.compile(
    r"(?<!\S)#([^\W_][\w-]*|_[\w-]*|[0-9][\w-]*)(?:=(\"[^\"]*\"|'[^']*'|[^\s]+))?",
    re.UNICODE,
)
DATE_TOKEN_RE = re.compile(
    r"->\s+("
    r"\d{4}-\d{2}-\d{2}|\d{4}/\d{2}/\d{2}|"
    r"\d{4}-\d{2}|\d{4}/\d{2}|"
    r"\d{4}-W\d{2}|\d{4}/W\d{2}|"
    r"\d{4}-Q[1-4]|"
    r"\d{4}"
    r")(?![A-Za-z0-9_/-])"
)


class XitError(Exception):
    pass


def fail(message):
    print(message, file=sys.stderr)
    return 1


def ensure_xit(path):
    if not path.endswith(".xit"):
        raise XitError(f"unsupported file extension: {path}")


def require_existing_xit(path):
    ensure_xit(path)
    if not os.path.exists(path):
        raise XitError(f"missing source file: {path}")


def parse_date_token(raw):
    s = raw.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            y, m, d = map(int, s.split("-"))
            return date(y, m, d).isoformat()
        if re.fullmatch(r"\d{4}/\d{2}/\d{2}", s):
            y, m, d = map(int, s.split("/"))
            return date(y, m, d).isoformat()
        if re.fullmatch(r"\d{4}-\d{2}", s):
            y, m = map(int, s.split("-"))
            return date(y, m, calendar.monthrange(y, m)[1]).isoformat()
        if re.fullmatch(r"\d{4}/\d{2}", s):
            y, m = map(int, s.split("/"))
            return date(y, m, calendar.monthrange(y, m)[1]).isoformat()
        if re.fullmatch(r"\d{4}", s):
            return date(int(s), 12, 31).isoformat()
        if re.fullmatch(r"\d{4}[-/]W\d{2}", s):
            y = int(s[:4])
            w = int(s[-2:])
            return date.fromisocalendar(y, w, 7).isoformat()
        if re.fullmatch(r"\d{4}-Q[1-4]", s):
            y = int(s[:4])
            q = int(s[-1])
            m = q * 3
            return date(y, m, calendar.monthrange(y, m)[1]).isoformat()
    except ValueError:
        pass
    raise XitError(f"invalid date: {raw}")


def find_due(description):
    for match in DATE_TOKEN_RE.finditer(description):
        try:
            return parse_date_token(match.group(1))
        except XitError:
            continue
    return None


def strip_due_tokens(text):
    return DATE_TOKEN_RE.sub("", text)


def parse_tag_arg(raw):
    token = raw.strip()
    if not token or token.startswith("#"):
        raise XitError(f"invalid tag: {raw}")
    if "=" not in token:
        name, value = token, None
    else:
        name, value = token.split("=", 1)
        if (len(value) >= 2) and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
    if not re.fullmatch(r"[\w-]+", name, re.UNICODE):
        raise XitError(f"invalid tag: {raw}")
    return name, value


def parse_tags(description):
    tags = {}
    for match in TAG_RE.finditer(description):
        name = match.group(1)
        value = match.group(2)
        if value is None:
            tags[name] = None
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            tags[name] = value[1:-1]
        else:
            tags[name] = value
    return tags


def strip_tag_tokens(text):
    return TAG_RE.sub("", text)


def compact_spaces(text):
    lines = []
    for line in text.split("\n"):
        lines.append(re.sub(r" {2,}", " ", line).strip())
    return "\n".join(lines).strip()


def split_priority(text):
    if text == "":
        return 0, ""
    parts = text.split(" ", 1)
    token = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    match = PRIORITY_RE.fullmatch(token)
    if not match:
        return 0, text
    bangs = match.group(1) or match.group(3) or ""
    return len(bangs), rest


def read_lines(path, missing_ok=False):
    if not os.path.exists(path):
        if missing_ok:
            return []
        raise XitError(f"missing source file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines(keepends=True)


def line_text(line):
    return line[:-1] if line.endswith("\n") else line


def parse_file(path, supplied_path, start_id=1, require_exists=True):
    ensure_xit(path)
    if require_exists:
        lines = read_lines(path)
    else:
        lines = read_lines(path, missing_ok=True)
    tasks = []
    i = 0
    next_id = start_id
    while i < len(lines):
        raw = line_text(lines[i])
        match = TASK_RE.match(raw)
        if not match:
            i += 1
            continue
        checkbox = match.group(1)
        initial = match.group(2) or ""
        priority, first_desc = split_priority(initial)
        cont = []
        j = i + 1
        while j < len(lines):
            nxt = line_text(lines[j])
            if nxt.startswith("    "):
                cont.append(nxt[4:])
                j += 1
            else:
                break
        description = first_desc
        if cont:
            description = description + ("\n" if description else "") + "\n".join(cont)
        task = {
            "id": next_id,
            "file": supplied_path,
            "line": i + 1,
            "status": CHECKBOX_STATUS[checkbox],
            "description": description,
            "priority": priority,
            "due": find_due(description),
            "tags": parse_tags(description),
            "_start": i,
            "_end": j,
            "_lines": lines[i:j],
        }
        tasks.append(task)
        next_id += 1
        i = j
    return tasks, next_id


def parse_files(paths):
    tasks = []
    next_id = 1
    for path in paths:
        parsed, next_id = parse_file(path, path, next_id, True)
        tasks.extend(parsed)
    return tasks


def public_task(task):
    return {
        "id": task["id"],
        "file": task["file"],
        "line": task["line"],
        "status": task["status"],
        "description": task["description"],
        "priority": task["priority"],
        "due": task["due"],
        "tags": task["tags"],
    }


def json_print(value):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def validate_status(status):
    if status not in STATUSES:
        raise XitError(f"unsupported status: {status}")


def clean_base_description(description):
    text = strip_tag_tokens(strip_due_tokens(description))
    return compact_spaces(text)


def format_tag(name, value):
    if value is None:
        return f"#{name}"
    if value == "" or re.search(r"\s", value):
        escaped = value.replace('"', '\\"')
        return f'#{name}="{escaped}"'
    return f"#{name}={value}"


def render_task_line(status, description="", priority=0, due=None, tags=None):
    validate_status(status)
    parts = [STATUSES[status]]
    if priority and int(priority) > 0:
        parts.append("!" * int(priority))
    desc_lines = (description or "").split("\n")
    first_desc = desc_lines[0].strip() if desc_lines else ""
    if first_desc:
        parts.append(first_desc)
    if due:
        parts.append("->")
        parts.append(due)
    for name, value in (tags or []):
        parts.append(format_tag(name, value))
    first = " ".join(parts)
    continuation = [f"    {line}" for line in desc_lines[1:]]
    return [first + "\n"] + [line + "\n" for line in continuation]


def rewrite_task(path, task, new_lines):
    lines = read_lines(path)
    lines[task["_start"]:task["_end"]] = new_lines
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def find_task(path, task_id):
    tasks, _ = parse_file(path, path, 1, True)
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise XitError(f"task ID not found: {task_id}")


def append_lines(path, lines):
    existing = read_lines(path, missing_ok=True)
    if existing and not existing[-1].endswith("\n"):
        existing[-1] += "\n"
    existing.extend(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(existing)


def command_list(args):
    tasks = parse_files(args.file)
    if args.status:
        validate_status(args.status)
        tasks = [t for t in tasks if t["status"] == args.status]
    for tag in args.tag or []:
        name, _ = parse_tag_arg(tag)
        tasks = [t for t in tasks if name in t["tags"]]
    if args.priority_min is not None:
        tasks = [t for t in tasks if t["priority"] >= args.priority_min]
    if args.due_on:
        due = parse_date_token(args.due_on)
        tasks = [t for t in tasks if t["due"] == due]
    if args.due_by:
        due = parse_date_token(args.due_by)
        tasks = [t for t in tasks if t["due"] is not None and t["due"] <= due]
    reverse = args.order == "desc"
    if args.sort == "priority":
        tasks = sorted(tasks, key=lambda t: (t["priority"], t["id"]), reverse=False)
        if reverse:
            tasks = sorted(tasks, key=lambda t: (-t["priority"], t["id"]))
    elif args.sort == "due":
        if reverse:
            dated = sorted([t for t in tasks if t["due"] is not None], key=lambda t: (t["due"], -t["id"]), reverse=True)
            undated = sorted([t for t in tasks if t["due"] is None], key=lambda t: t["id"])
            tasks = undated + dated
        else:
            tasks = sorted(tasks, key=lambda t: (t["due"] is None, t["due"] or "", t["id"]))
    else:
        tasks = sorted(tasks, key=lambda t: t["id"], reverse=reverse)
    json_print([public_task(t) for t in tasks])


def command_stats(args):
    tasks = parse_files(args.file)
    result = {
        "total": len(tasks),
        "by_status": {},
        "by_priority": {},
        "by_file": {},
        "with_tags": 0,
        "with_due": 0,
    }
    for task in tasks:
        result["by_status"][task["status"]] = result["by_status"].get(task["status"], 0) + 1
        p = str(task["priority"])
        result["by_priority"][p] = result["by_priority"].get(p, 0) + 1
        result["by_file"][task["file"]] = result["by_file"].get(task["file"], 0) + 1
        if task["tags"]:
            result["with_tags"] += 1
        if task["due"] is not None:
            result["with_due"] += 1
    json_print(result)


def command_add(args):
    ensure_xit(args.file)
    validate_status(args.status)
    due = parse_date_token(args.due) if args.due else None
    tags = [parse_tag_arg(t) for t in (args.tag or [])]
    new_lines = render_task_line(args.status, args.text, args.priority, due, tags)
    append_lines(args.file, new_lines)
    tasks, _ = parse_file(args.file, args.file, 1, True)
    json_print(public_task(tasks[-1]))


def task_components_for_write(task):
    base = clean_base_description(task["description"])
    return base, task["priority"], task["due"], list(task["tags"].items())


def command_mark(args):
    require_existing_xit(args.file)
    validate_status(args.status)
    task = find_task(args.file, args.id)
    lines = list(task["_lines"])
    first = line_text(lines[0])
    lines[0] = STATUSES[args.status] + first[3:] + ("\n" if lines[0].endswith("\n") else "")
    rewrite_task(args.file, task, lines)
    updated = find_task(args.file, args.id)
    json_print(public_task(updated))


def command_tag(args):
    require_existing_xit(args.file)
    name, value = parse_tag_arg(args.tag)
    task = find_task(args.file, args.id)
    base, priority, due, tags = task_components_for_write(task)
    tags = [(n, v) for n, v in tags if n != name]
    tags.append((name, value))
    rewrite_task(args.file, task, render_task_line(task["status"], base, priority, due, tags))
    updated = find_task(args.file, args.id)
    json_print(public_task(updated))


def command_untag(args):
    require_existing_xit(args.file)
    name, _ = parse_tag_arg(args.tag)
    task = find_task(args.file, args.id)
    base, priority, due, tags = task_components_for_write(task)
    tags = [(n, v) for n, v in tags if n != name]
    rewrite_task(args.file, task, render_task_line(task["status"], base, priority, due, tags))
    updated = find_task(args.file, args.id)
    json_print(public_task(updated))


def command_reschedule(args):
    require_existing_xit(args.file)
    due = parse_date_token(args.date)
    task = find_task(args.file, args.id)
    base, priority, _, tags = task_components_for_write(task)
    rewrite_task(args.file, task, render_task_line(task["status"], base, priority, due, tags))
    updated = find_task(args.file, args.id)
    json_print(public_task(updated))


def command_move(args):
    require_existing_xit(args.src)
    ensure_xit(args.dst)
    task = find_task(args.src, args.id)
    moved_lines = deepcopy(task["_lines"])
    src_lines = read_lines(args.src)
    if os.path.abspath(args.src) == os.path.abspath(args.dst):
        del src_lines[task["_start"]:task["_end"]]
        if src_lines and not src_lines[-1].endswith("\n"):
            src_lines[-1] += "\n"
        src_lines.extend(moved_lines)
        with open(args.src, "w", encoding="utf-8") as f:
            f.writelines(src_lines)
    else:
        del src_lines[task["_start"]:task["_end"]]
        dst_lines = read_lines(args.dst, missing_ok=True)
        if dst_lines and not dst_lines[-1].endswith("\n"):
            dst_lines[-1] += "\n"
        dst_lines.extend(moved_lines)
        with open(args.src, "w", encoding="utf-8") as f:
            f.writelines(src_lines)
        with open(args.dst, "w", encoding="utf-8") as f:
            f.writelines(dst_lines)
    tasks, _ = parse_file(args.dst, args.dst, 1, True)
    json_print(public_task(tasks[-1]))


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise XitError(message)


def build_parser():
    parser = Parser(prog="xitlite.py")
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
    p.set_defaults(func=command_list)

    p = sub.add_parser("stats")
    p.add_argument("--file", action="append", required=True)
    p.set_defaults(func=command_stats)

    p = sub.add_parser("add")
    p.add_argument("--file", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--status", default="open")
    p.add_argument("--priority", type=int, default=0)
    p.add_argument("--due")
    p.add_argument("--tag", action="append")
    p.set_defaults(func=command_add)

    p = sub.add_parser("mark")
    p.add_argument("--file", required=True)
    p.add_argument("id", type=int)
    p.add_argument("--status", required=True)
    p.set_defaults(func=command_mark)

    p = sub.add_parser("tag")
    p.add_argument("--file", required=True)
    p.add_argument("id", type=int)
    p.add_argument("tag")
    p.set_defaults(func=command_tag)

    p = sub.add_parser("untag")
    p.add_argument("--file", required=True)
    p.add_argument("id", type=int)
    p.add_argument("tag")
    p.set_defaults(func=command_untag)

    p = sub.add_parser("reschedule")
    p.add_argument("--file", required=True)
    p.add_argument("id", type=int)
    p.add_argument("date")
    p.set_defaults(func=command_reschedule)

    p = sub.add_parser("move")
    p.add_argument("--from", dest="src", required=True)
    p.add_argument("--to", dest="dst", required=True)
    p.add_argument("id", type=int)
    p.set_defaults(func=command_move)
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        args.func(args)
        return 0
    except XitError as exc:
        return fail(str(exc))
    except BrokenPipeError:
        return 1


if __name__ == "__main__":
    sys.exit(main())

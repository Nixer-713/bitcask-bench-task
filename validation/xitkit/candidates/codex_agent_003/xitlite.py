#!/usr/bin/env python3
import argparse
import calendar
import json
import os
import re
import sys
from datetime import date
from functools import cmp_to_key


STATUSES = {
    "open": "[ ]",
    "done": "[x]",
    "ongoing": "[@]",
    "obsolete": "[~]",
    "question": "[?]",
}
BOX_TO_STATUS = {v: k for k, v in STATUSES.items()}
PRIORITY_RE = re.compile(r"^(\.+!+|!+\. *)(?=$|[^.!])".replace(" ", ""))
TAG_RE = re.compile(r"(?<![\w-])#(?P<name>[\w-][\w-]*)(?:=(?P<value>\"[^\"]*\"|'[^']*'|[^\s#]+))?", re.UNICODE)
DATE_RE = re.compile(
    r"-> ("
    r"\d{4}[-/]\d{2}[-/]\d{2}|"
    r"\d{4}[-/][Ww]\d{2}|"
    r"\d{4}[-/]\d{2}|"
    r"\d{4}-[Qq][1-4]|"
    r"\d{4}"
    r")(?![A-Za-z0-9/_-])"
)


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def emit(value):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def public_task(task):
    return {
        "id": task["id"],
        "file": task["file"],
        "line": task["line"],
        "status": task["status"],
        "description": task["description"],
        "priority": task["priority"],
        "due": task["due"],
        "tags": dict(task["tags"]),
    }


def require_xit(path):
    if os.path.splitext(path)[1] != ".xit":
        fail(f"unsupported file extension: {path}")


def read_lines(path):
    require_xit(path)
    if not os.path.exists(path):
        fail(f"missing source file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def normalize_date(value):
    value = str(value)
    try:
        if re.fullmatch(r"\d{4}[-/]\d{2}[-/]\d{2}", value):
            delim = "-" if "-" in value else "/"
            y, m, d = map(int, value.split(delim))
            return date(y, m, d).isoformat()
        if re.fullmatch(r"\d{4}[-/]\d{2}", value):
            delim = "-" if "-" in value else "/"
            y, m = map(int, value.split(delim))
            return date(y, m, calendar.monthrange(y, m)[1]).isoformat()
        if re.fullmatch(r"\d{4}[-/][Ww]\d{2}", value):
            delim = "-" if "-" in value else "/"
            y_s, w_s = value.split(delim)
            return date.fromisocalendar(int(y_s), int(w_s[1:]), 7).isoformat()
        if re.fullmatch(r"\d{4}-[Qq][1-4]", value):
            y = int(value[:4])
            q = int(value[-1])
            m = q * 3
            return date(y, m, calendar.monthrange(y, m)[1]).isoformat()
        if re.fullmatch(r"\d{4}", value):
            return date(int(value), 12, 31).isoformat()
    except ValueError:
        return None
    return None


def require_date(value):
    normalized = normalize_date(value)
    if normalized is None:
        fail(f"invalid date: {value}")
    return normalized


def is_continuation(line):
    body = line[:-1] if line.endswith("\n") else line
    if not body.startswith("    "):
        return False
    return len(body) == 4 or body[4] != " "


def split_first_line_text(line):
    text = line[:-1] if line.endswith("\n") else line
    box = text[:3]
    if box not in BOX_TO_STATUS:
        return None
    if len(text) == 3:
        return box, ""
    if len(text) > 3 and text[3] == " ":
        return box, text[4:]
    return None


def parse_priority(text):
    match = PRIORITY_RE.match(text)
    if not match:
        return 0, text
    token = match.group(1)
    rest = text[match.end() :]
    if rest.startswith(" "):
        rest = rest[1:]
    return token.count("!"), rest


def parse_tags(description):
    tags = {}
    order = []
    for match in TAG_RE.finditer(description):
        name = match.group("name")
        raw = match.group("value")
        if raw is None:
            value = None
        elif len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
            value = raw[1:-1]
        else:
            value = raw
        if name not in tags:
            order.append(name)
        tags[name] = value
    return tags, order


def parse_due(description):
    for match in DATE_RE.finditer(description):
        normalized = normalize_date(match.group(1))
        if normalized is not None:
            return normalized
    return None


def parse_lines(lines, file_arg, first_id=1):
    tasks = []
    i = 0
    next_id = first_id
    while i < len(lines):
        split = split_first_line_text(lines[i])
        if split is None:
            i += 1
            continue

        box, first_text = split
        priority, first_description = parse_priority(first_text)
        desc_parts = [first_description]
        end = i + 1
        while end < len(lines) and is_continuation(lines[end]):
            cont = lines[end][4:]
            if cont.endswith("\n"):
                cont = cont[:-1]
            desc_parts.append(cont)
            end += 1

        description = "\n".join(desc_parts)
        tags, tag_order = parse_tags(description)
        task = {
            "id": next_id,
            "file": file_arg,
            "line": i + 1,
            "status": BOX_TO_STATUS[box],
            "description": description,
            "priority": priority,
            "due": parse_due(description),
            "tags": tags,
            "_tag_order": tag_order,
            "_start": i,
            "_end": end,
            "_raw": lines[i:end],
        }
        tasks.append(task)
        next_id += 1
        i = end
    return tasks, next_id


def parse_files(paths):
    all_tasks = []
    next_id = 1
    for path in paths:
        lines = read_lines(path)
        tasks, next_id = parse_lines(lines, path, next_id)
        all_tasks.extend(tasks)
    return all_tasks


def parse_one_file(path):
    lines = read_lines(path)
    tasks, _ = parse_lines(lines, path, 1)
    return lines, tasks


def find_task(tasks, task_id):
    for task in tasks:
        if task["id"] == task_id:
            return task
    fail(f"task ID not found: {task_id}")


def remove_metadata(description):
    spans = []
    for match in DATE_RE.finditer(description):
        if normalize_date(match.group(1)) is not None:
            spans.append(match.span())
    spans.extend(match.span() for match in TAG_RE.finditer(description))
    if not spans:
        return description
    chars = list(description)
    for start, end in spans:
        for idx in range(start, end):
            chars[idx] = " "
    cleaned_lines = []
    for line in "".join(chars).split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def format_tag(name, value):
    if value is None:
        return f"#{name}"
    value = str(value)
    if value == "" or re.search(r"\s|#", value):
        escaped = value.replace('"', r"\"")
        return f'#{name}="{escaped}"'
    return f"#{name}={value}"


def canonical_block(status, body, priority=0, due=None, tags=None, tag_order=None):
    tags = tags or {}
    tag_order = tag_order or list(tags.keys())
    body_lines = str(body).split("\n") if body is not None else [""]
    first = body_lines[0] if body_lines else ""

    parts = [STATUSES[status]]
    if priority:
        parts.append("!" * int(priority))
    suffix = []
    if first:
        suffix.append(first)
    if due:
        suffix.append(f"-> {due}")
    for name in tag_order:
        if name in tags:
            suffix.append(format_tag(name, tags[name]))
    if suffix:
        parts.append(" ".join(suffix))

    out = [" ".join(parts) + "\n"]
    for line in body_lines[1:]:
        out.append("    " + line + "\n")
    return out


def write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def parse_tag_argument(arg):
    if arg.startswith("#"):
        fail(f"invalid tag argument: {arg}")
    match = re.fullmatch(r"([\w-][\w-]*)(?:=(.*))?", arg, re.UNICODE)
    if not match:
        fail(f"invalid tag argument: {arg}")
    name = match.group(1)
    raw = match.group(2)
    if raw is None:
        return name, None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return name, raw[1:-1]
    return name, raw


def validate_status(status):
    if status not in STATUSES:
        fail(f"unsupported status: {status}")
    return status


def validate_priority(priority):
    try:
        value = int(priority)
    except (TypeError, ValueError):
        fail(f"invalid priority: {priority}")
    if value < 0:
        fail(f"invalid priority: {priority}")
    return value


def cmp_tasks(sort_key, order):
    def compare(a, b):
        if sort_key == "id":
            av, bv = a["id"], b["id"]
        elif sort_key == "priority":
            av, bv = a["priority"], b["priority"]
        else:
            av, bv = a["due"], b["due"]
            if av is None and bv is None:
                return a["id"] - b["id"]
            if av is None:
                return 1 if order == "asc" else -1
            if bv is None:
                return -1 if order == "asc" else 1
        if av < bv:
            result = -1
        elif av > bv:
            result = 1
        else:
            result = 0
        if order == "desc":
            result = -result
        if result == 0:
            return a["id"] - b["id"]
        return result

    return compare


def command_list(args):
    tasks = parse_files(args.file)
    if args.status is not None:
        validate_status(args.status)
        tasks = [task for task in tasks if task["status"] == args.status]
    for tag_arg in args.tag or []:
        name, _ = parse_tag_argument(tag_arg)
        tasks = [task for task in tasks if name in task["tags"]]
    if args.priority_min is not None:
        minimum = validate_priority(args.priority_min)
        tasks = [task for task in tasks if task["priority"] >= minimum]
    if args.due_on is not None:
        due_on = require_date(args.due_on)
        tasks = [task for task in tasks if task["due"] == due_on]
    if args.due_by is not None:
        due_by = require_date(args.due_by)
        tasks = [task for task in tasks if task["due"] is not None and task["due"] <= due_by]
    tasks = sorted(tasks, key=cmp_to_key(cmp_tasks(args.sort, args.order)))
    emit([public_task(task) for task in tasks])


def command_stats(args):
    tasks = parse_files(args.file)
    stats = {
        "total": len(tasks),
        "by_status": {},
        "by_priority": {},
        "by_file": {},
        "with_tags": 0,
        "with_due": 0,
    }
    for task in tasks:
        stats["by_status"][task["status"]] = stats["by_status"].get(task["status"], 0) + 1
        p_key = str(task["priority"])
        stats["by_priority"][p_key] = stats["by_priority"].get(p_key, 0) + 1
        stats["by_file"][task["file"]] = stats["by_file"].get(task["file"], 0) + 1
        if task["tags"]:
            stats["with_tags"] += 1
        if task["due"] is not None:
            stats["with_due"] += 1
    emit(stats)


def command_add(args):
    path = args.file
    require_xit(path)
    status = validate_status(args.status)
    priority = validate_priority(args.priority)
    due = require_date(args.due) if args.due else None
    tags = {}
    order = []
    for tag_arg in args.tag or []:
        name, value = parse_tag_argument(tag_arg)
        if name not in tags:
            order.append(name)
        tags[name] = value

    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    block = canonical_block(status, args.text, priority, due, tags, order)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines.extend(block)
    write_lines(path, lines)
    _, tasks = parse_one_file(path)
    emit(public_task(tasks[-1]))


def command_mark(args):
    validate_status(args.status)
    lines, tasks = parse_one_file(args.file)
    task = find_task(tasks, args.id)
    idx = task["_start"]
    old = lines[idx]
    lines[idx] = STATUSES[args.status] + old[3:]
    write_lines(args.file, lines)
    _, updated = parse_one_file(args.file)
    emit(public_task(find_task(updated, args.id)))


def rewrite_task(args, transform):
    lines, tasks = parse_one_file(args.file)
    task = find_task(tasks, args.id)
    body = remove_metadata(task["description"])
    tags = dict(task["tags"])
    order = list(task["_tag_order"])
    due = task["due"]
    body, tags, order, due = transform(body, tags, order, due)
    block = canonical_block(task["status"], body, task["priority"], due, tags, order)
    lines[task["_start"] : task["_end"]] = block
    write_lines(args.file, lines)
    _, updated = parse_one_file(args.file)
    emit(public_task(find_task(updated, args.id)))


def command_tag(args):
    name, value = parse_tag_argument(args.tag_value)

    def transform(body, tags, order, due):
        if name not in tags:
            order.append(name)
        tags[name] = value
        return body, tags, order, due

    rewrite_task(args, transform)


def command_untag(args):
    name, _ = parse_tag_argument(args.tag_value)

    def transform(body, tags, order, due):
        tags.pop(name, None)
        order = [item for item in order if item != name]
        return body, tags, order, due

    rewrite_task(args, transform)


def command_reschedule(args):
    new_due = require_date(args.date_value)

    def transform(body, tags, order, due):
        return body, tags, order, new_due

    rewrite_task(args, transform)


def same_file(a, b):
    try:
        return os.path.abspath(a) == os.path.abspath(b)
    except OSError:
        return False


def command_move(args):
    require_xit(args.from_file)
    require_xit(args.to_file)
    source_lines, source_tasks = parse_one_file(args.from_file)
    task = find_task(source_tasks, args.id)
    raw = list(task["_raw"])

    if same_file(args.from_file, args.to_file):
        new_lines = source_lines[: task["_start"]] + source_lines[task["_end"] :]
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.extend(raw)
        write_lines(args.from_file, new_lines)
    else:
        target_lines = []
        if os.path.exists(args.to_file):
            with open(args.to_file, "r", encoding="utf-8") as f:
                target_lines = f.readlines()
        new_source = source_lines[: task["_start"]] + source_lines[task["_end"] :]
        if target_lines and not target_lines[-1].endswith("\n"):
            target_lines[-1] += "\n"
        target_lines.extend(raw)
        write_lines(args.from_file, new_source)
        write_lines(args.to_file, target_lines)

    _, target_tasks = parse_one_file(args.to_file)
    if not target_tasks:
        fail("moved task was not parseable")
    emit(public_task(target_tasks[-1]))


def build_parser():
    parser = argparse.ArgumentParser(prog="xitlite.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list")
    p.add_argument("--file", action="append", required=True)
    p.add_argument("--status")
    p.add_argument("--tag", action="append")
    p.add_argument("--priority-min", dest="priority_min")
    p.add_argument("--due-on", dest="due_on")
    p.add_argument("--due-by", dest="due_by")
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
    p.add_argument("--priority", default=0)
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
    p.add_argument("tag_value")
    p.set_defaults(func=command_tag)

    p = sub.add_parser("untag")
    p.add_argument("--file", required=True)
    p.add_argument("id", type=int)
    p.add_argument("tag_value")
    p.set_defaults(func=command_untag)

    p = sub.add_parser("reschedule")
    p.add_argument("--file", required=True)
    p.add_argument("id", type=int)
    p.add_argument("date_value")
    p.set_defaults(func=command_reschedule)

    p = sub.add_parser("move")
    p.add_argument("--from", dest="from_file", required=True)
    p.add_argument("--to", dest="to_file", required=True)
    p.add_argument("id", type=int)
    p.set_defaults(func=command_move)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

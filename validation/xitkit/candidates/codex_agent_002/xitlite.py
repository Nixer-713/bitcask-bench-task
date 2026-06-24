#!/usr/bin/env python3
import argparse
import calendar
import datetime as dt
import json
import os
import re
import sys
from functools import cmp_to_key


STATUS_TO_BOX = {
    "open": "[ ]",
    "done": "[x]",
    "ongoing": "[@]",
    "obsolete": "[~]",
    "question": "[?]",
}
BOX_TO_STATUS = {v: k for k, v in STATUS_TO_BOX.items()}
STATUSES = tuple(STATUS_TO_BOX)

TASK_RE = re.compile(r"^(\[ \]|\[x\]|\[@\]|\[~\]|\[\?\])(?:$| (.*)$)")
PRIORITY_RE = re.compile(r"(?:!+|\.+!+|!+\.+)")
DATE_TOKEN_RE = re.compile(
    r"-> ("
    r"\d{4}[-/]\d{2}[-/]\d{2}|"
    r"\d{4}[-/][Ww]\d{2}|"
    r"\d{4}-[Qq][1-4]|"
    r"\d{4}[-/]\d{2}|"
    r"\d{4}"
    r")(?![A-Za-z0-9_/-])"
)
TAG_RE = re.compile(
    r"#(?P<name>[\w-]+)"
    r"(?:=(?:\"(?P<dq>[^\"]*)\"|'(?P<sq>[^']*)'|(?P<bare>[^\s#]*)))?",
    re.UNICODE,
)
COMMAND_TAG_RE = re.compile(
    r"^(?P<name>[\w-]+)(?:=(?:\"(?P<dq>[^\"]*)\"|'(?P<sq>[^']*)'|(?P<bare>.*)))?$",
    re.UNICODE,
)


class CLIError(Exception):
    pass


def compact_json(value):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def fail(message):
    raise CLIError(message)


def validate_xit_path(path):
    if os.path.splitext(path)[1] != ".xit":
        fail(f"unsupported file extension: {path}")


def read_lines(path, *, required=True):
    validate_xit_path(path)
    if not os.path.exists(path):
        if required:
            fail(f"missing source file: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def write_lines(path, lines):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp_path = None
    try:
        import tempfile

        fd, tmp_path = tempfile.mkstemp(prefix=".xitlite.", dir=directory, text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(tmp_path, path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def split_newline(line):
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def is_continuation(line):
    body, _ = split_newline(line)
    return body.startswith("    ") and not body.startswith("     ")


def parse_priority(text):
    if not text:
        return 0, text
    m = re.match(r"\S+", text)
    if not m:
        return 0, text
    token = m.group(0)
    if not PRIORITY_RE.fullmatch(token):
        return 0, text
    rest = text[m.end() :]
    if rest.startswith(" "):
        rest = rest[1:]
    return token.count("!"), rest


def normalize_date_token(token):
    token = token.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
            d = dt.date.fromisoformat(token)
            return d.isoformat()
        if re.fullmatch(r"\d{4}/\d{2}/\d{2}", token):
            y, m, d = map(int, token.split("/"))
            return dt.date(y, m, d).isoformat()
        if re.fullmatch(r"\d{4}-\d{2}", token):
            y, m = map(int, token.split("-"))
            return dt.date(y, m, calendar.monthrange(y, m)[1]).isoformat()
        if re.fullmatch(r"\d{4}/\d{2}", token):
            y, m = map(int, token.split("/"))
            return dt.date(y, m, calendar.monthrange(y, m)[1]).isoformat()
        if re.fullmatch(r"\d{4}", token):
            return dt.date(int(token), 12, 31).isoformat()
        if re.fullmatch(r"\d{4}-[Ww]\d{2}", token):
            y, w = token.split("-")
            return dt.date.fromisocalendar(int(y), int(w[1:]), 7).isoformat()
        if re.fullmatch(r"\d{4}/[Ww]\d{2}", token):
            y, w = token.split("/")
            return dt.date.fromisocalendar(int(y), int(w[1:]), 7).isoformat()
        if re.fullmatch(r"\d{4}-[Qq][1-4]", token):
            y = int(token[:4])
            q = int(token[-1])
            month = q * 3
            return dt.date(y, month, calendar.monthrange(y, month)[1]).isoformat()
    except ValueError:
        return None
    return None


def normalize_date_arg(token):
    value = normalize_date_token(token)
    if value is None:
        fail(f"invalid date argument: {token}")
    return value


def extract_due(description):
    for m in DATE_TOKEN_RE.finditer(description):
        value = normalize_date_token(m.group(1))
        if value is not None:
            return value
    return None


def tag_value_from_match(m):
    if m.group("dq") is not None:
        return m.group("dq")
    if m.group("sq") is not None:
        return m.group("sq")
    if m.group("bare") is not None:
        return m.group("bare")
    return None


def extract_tags(description):
    tags = {}
    for m in TAG_RE.finditer(description):
        tags[m.group("name")] = tag_value_from_match(m)
    return tags


def parse_task_tag(arg):
    if arg.startswith("#"):
        fail(f"tag argument must not start with #: {arg}")
    m = COMMAND_TAG_RE.fullmatch(arg)
    if not m:
        fail(f"invalid tag argument: {arg}")
    name = m.group("name")
    if not name:
        fail(f"invalid tag argument: {arg}")
    return name, tag_value_from_match(m)


def parse_lines(lines, supplied_path):
    tasks = []
    i = 0
    while i < len(lines):
        body, _ = split_newline(lines[i])
        m = TASK_RE.match(body)
        if not m:
            i += 1
            continue
        checkbox, first_text = m.group(1), m.group(2)
        first_text = first_text if first_text is not None else ""
        j = i + 1
        continuation = []
        while j < len(lines) and is_continuation(lines[j]):
            cont_body, _ = split_newline(lines[j])
            continuation.append(cont_body[4:])
            j += 1
        priority, first_desc = parse_priority(first_text)
        parts = [first_desc] + continuation
        description = "\n".join(parts)
        task = {
            "id": len(tasks) + 1,
            "file": supplied_path,
            "line": i + 1,
            "status": BOX_TO_STATUS[checkbox],
            "description": description,
            "priority": priority,
            "due": extract_due(description),
            "tags": extract_tags(description),
            "_start": i,
            "_end": j,
        }
        tasks.append(task)
        i = j
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


def parse_files(paths):
    all_tasks = []
    for path in paths:
        lines = read_lines(path, required=True)
        for task in parse_lines(lines, path):
            task = dict(task)
            task["id"] = len(all_tasks) + 1
            all_tasks.append(task)
    return all_tasks


def find_task(tasks, task_id):
    for task in tasks:
        if task["id"] == task_id:
            return task
    fail(f"task ID not found: {task_id}")


def clean_description_text(description):
    lines = []
    for line in description.split("\n"):
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        lines.append(line)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def remove_due_tokens(description):
    def repl(match):
        if normalize_date_token(match.group(1)) is None:
            return match.group(0)
        return ""

    return DATE_TOKEN_RE.sub(repl, description)


def strip_due_and_tags(description):
    text = remove_due_tokens(description)
    text = TAG_RE.sub("", text)
    return clean_description_text(text)


def strip_due(description):
    return clean_description_text(remove_due_tokens(description))


def ordered_tags_from_task(task):
    return list(task["tags"].items())


def format_tag(name, value):
    if value is None:
        return f"#{name}"
    if value == "" or re.search(r"\s|['\"]", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'#{name}="{escaped}"'
    return f"#{name}={value}"


def format_task_lines(status, priority, description, due, tag_items):
    chunks = []
    if priority:
        chunks.append("!" * int(priority))
    desc_lines = description.split("\n") if description else [""]
    first_desc = desc_lines[0].strip()
    if first_desc:
        chunks.append(first_desc)
    if due:
        chunks.append(f"-> {due}")
    for name, value in tag_items:
        chunks.append(format_tag(name, value))

    first_line = STATUS_TO_BOX[status]
    if chunks:
        first_line += " " + " ".join(chunks)
    result = [first_line + "\n"]
    for continuation in desc_lines[1:]:
        result.append("    " + continuation.strip() + "\n")
    return result


def replace_task_block(lines, task, new_task_lines):
    return lines[: task["_start"]] + new_task_lines + lines[task["_end"] :]


def task_from_file(path, task_id):
    lines = read_lines(path, required=True)
    tasks = parse_lines(lines, path)
    task = find_task(tasks, task_id)
    return lines, tasks, task


def cmd_list(args):
    tasks = [public_task(t) for t in parse_files(args.file)]
    if args.status:
        tasks = [t for t in tasks if t["status"] == args.status]
    for tag in args.tag or []:
        name, _ = parse_task_tag(tag)
        tasks = [t for t in tasks if name in t["tags"]]
    if args.priority_min is not None:
        tasks = [t for t in tasks if t["priority"] >= args.priority_min]
    if args.due_on:
        due_on = normalize_date_arg(args.due_on)
        tasks = [t for t in tasks if t["due"] == due_on]
    if args.due_by:
        due_by = normalize_date_arg(args.due_by)
        tasks = [t for t in tasks if t["due"] is not None and t["due"] <= due_by]

    sort_name = args.sort
    order = args.order

    def compare(a, b):
        if sort_name == "id":
            av, bv = a["id"], b["id"]
        elif sort_name == "priority":
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
            primary = -1
        elif av > bv:
            primary = 1
        else:
            primary = 0
        if order == "desc":
            primary = -primary
        if primary:
            return primary
        return a["id"] - b["id"]

    tasks.sort(key=cmp_to_key(compare))
    compact_json(tasks)


def cmd_stats(args):
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
        p = str(task["priority"])
        stats["by_priority"][p] = stats["by_priority"].get(p, 0) + 1
        stats["by_file"][task["file"]] = stats["by_file"].get(task["file"], 0) + 1
        if task["tags"]:
            stats["with_tags"] += 1
        if task["due"] is not None:
            stats["with_due"] += 1
    compact_json(stats)


def cmd_add(args):
    validate_xit_path(args.file)
    due = normalize_date_arg(args.due) if args.due else None
    tag_items = [parse_task_tag(t) for t in (args.tag or [])]
    if args.priority is not None and args.priority < 0:
        fail("priority must be non-negative")
    lines = read_lines(args.file, required=False)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines.extend(format_task_lines(args.status, args.priority or 0, args.text, due, tag_items))
    write_lines(args.file, lines)
    tasks = parse_lines(read_lines(args.file, required=True), args.file)
    compact_json(public_task(tasks[-1]))


def cmd_mark(args):
    lines, _, task = task_from_file(args.file, args.id)
    body, newline = split_newline(lines[task["_start"]])
    new_body = STATUS_TO_BOX[args.status] + body[3:]
    lines[task["_start"]] = new_body + (newline or "\n")
    write_lines(args.file, lines)
    updated = find_task(parse_lines(read_lines(args.file, required=True), args.file), args.id)
    compact_json(public_task(updated))


def cmd_tag(args):
    lines, _, task = task_from_file(args.file, args.id)
    name, value = parse_task_tag(args.tag_arg)
    tags = ordered_tags_from_task(task)
    replaced = False
    for idx, (old_name, _) in enumerate(tags):
        if old_name == name:
            tags[idx] = (name, value)
            replaced = True
            break
    if not replaced:
        tags.append((name, value))
    description = strip_due_and_tags(task["description"])
    new_lines = format_task_lines(task["status"], task["priority"], description, task["due"], tags)
    write_lines(args.file, replace_task_block(lines, task, new_lines))
    updated = find_task(parse_lines(read_lines(args.file, required=True), args.file), args.id)
    compact_json(public_task(updated))


def cmd_untag(args):
    lines, _, task = task_from_file(args.file, args.id)
    name, _ = parse_task_tag(args.tag_arg)
    tags = [(n, v) for n, v in ordered_tags_from_task(task) if n != name]
    description = strip_due_and_tags(task["description"])
    new_lines = format_task_lines(task["status"], task["priority"], description, task["due"], tags)
    write_lines(args.file, replace_task_block(lines, task, new_lines))
    updated = find_task(parse_lines(read_lines(args.file, required=True), args.file), args.id)
    compact_json(public_task(updated))


def cmd_reschedule(args):
    new_due = normalize_date_arg(args.date)
    lines, _, task = task_from_file(args.file, args.id)
    description = strip_due_and_tags(task["description"])
    tags = ordered_tags_from_task(task)
    new_lines = format_task_lines(task["status"], task["priority"], description, new_due, tags)
    write_lines(args.file, replace_task_block(lines, task, new_lines))
    updated = find_task(parse_lines(read_lines(args.file, required=True), args.file), args.id)
    compact_json(public_task(updated))


def cmd_move(args):
    validate_xit_path(args.to_file)
    source_lines, _, task = task_from_file(args.from_file, args.id)
    target_lines = read_lines(args.to_file, required=False)
    if target_lines and not target_lines[-1].endswith("\n"):
        target_lines[-1] += "\n"
    task_block = source_lines[task["_start"] : task["_end"]]
    new_source = source_lines[: task["_start"]] + source_lines[task["_end"] :]
    new_target = target_lines + task_block
    write_lines(args.to_file, new_target)
    write_lines(args.from_file, new_source)
    target_tasks = parse_lines(read_lines(args.to_file, required=True), args.to_file)
    compact_json(public_task(target_tasks[-1]))


def build_parser():
    parser = argparse.ArgumentParser(prog="xitlite.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list")
    p.add_argument("--file", action="append", required=True)
    p.add_argument("--status", choices=STATUSES)
    p.add_argument("--tag", action="append")
    p.add_argument("--priority-min", type=int)
    p.add_argument("--due-on")
    p.add_argument("--due-by")
    p.add_argument("--sort", choices=("id", "priority", "due"), default="id")
    p.add_argument("--order", choices=("asc", "desc"), default="asc")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("stats")
    p.add_argument("--file", action="append", required=True)
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("add")
    p.add_argument("--file", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--status", choices=STATUSES, default="open")
    p.add_argument("--priority", type=int, default=0)
    p.add_argument("--due")
    p.add_argument("--tag", action="append")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("mark")
    p.add_argument("--file", required=True)
    p.add_argument("id", type=int)
    p.add_argument("--status", choices=STATUSES, required=True)
    p.set_defaults(func=cmd_mark)

    p = sub.add_parser("tag")
    p.add_argument("--file", required=True)
    p.add_argument("id", type=int)
    p.add_argument("tag_arg", metavar="TAG")
    p.set_defaults(func=cmd_tag)

    p = sub.add_parser("untag")
    p.add_argument("--file", required=True)
    p.add_argument("id", type=int)
    p.add_argument("tag_arg", metavar="TAG")
    p.set_defaults(func=cmd_untag)

    p = sub.add_parser("reschedule")
    p.add_argument("--file", required=True)
    p.add_argument("id", type=int)
    p.add_argument("date", metavar="DATE")
    p.set_defaults(func=cmd_reschedule)

    p = sub.add_parser("move")
    p.add_argument("--from", dest="from_file", required=True)
    p.add_argument("--to", dest="to_file", required=True)
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_move)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except CLIError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

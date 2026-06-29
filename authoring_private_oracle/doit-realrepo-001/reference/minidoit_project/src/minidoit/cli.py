from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

from . import __version__


COMMANDS = {"run", "list", "info", "clean", "forget", "dumpdb"}
ALLOWED_FIELDS = {
    "actions",
    "file_dep",
    "targets",
    "task_dep",
    "clean",
    "uptodate",
    "doc",
    "verbosity",
}
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class MiniDoitError(Exception):
    pass


@dataclass
class Task:
    name: str
    actions: list[str]
    file_dep: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    task_dep: list[str] = field(default_factory=list)
    clean: Any = False
    uptodate: Any = None
    doc: str = ""
    verbosity: int | None = None


@dataclass
class Options:
    command: str
    rest: list[str]
    task_file: Path
    db_file: Path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if "--help" in argv or "-h" in argv:
            print_help()
            return 0
        if "--version" in argv:
            print(__version__)
            return 0

        opts = parse_args(argv)
        if opts.command == "dumpdb":
            return cmd_dumpdb(opts)

        tasks = load_tasks(opts.task_file)
        if opts.command == "list":
            return cmd_list(opts, tasks)
        if opts.command == "info":
            return cmd_info(opts, tasks)
        if opts.command == "run":
            return cmd_run(opts, tasks)
        if opts.command == "clean":
            return cmd_clean(opts, tasks)
        if opts.command == "forget":
            return cmd_forget(opts, tasks)
        raise MiniDoitError(f"unsupported command: {opts.command}")
    except MiniDoitError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def print_help() -> None:
    print(
        "minidoit [--file FILE] [--db-file FILE] [run|list|info|clean|forget|dumpdb] "
        "[--json] [--status] [--forget] [--all] [TASK ...]"
    )


def parse_args(argv: list[str]) -> Options:
    file_arg: str | None = None
    db_arg: str | None = None
    remaining: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--file":
            i += 1
            if i >= len(argv):
                raise MiniDoitError("--file requires a value")
            file_arg = argv[i]
        elif arg == "--db-file":
            i += 1
            if i >= len(argv):
                raise MiniDoitError("--db-file requires a value")
            db_arg = argv[i]
        else:
            remaining.append(arg)
        i += 1

    config_task, config_db = load_config(Path.cwd())
    task_file = Path(file_arg) if file_arg else config_task
    db_file = Path(db_arg) if db_arg else config_db

    if remaining and remaining[0] in COMMANDS:
        command = remaining[0]
        rest = remaining[1:]
    else:
        command = "run"
        rest = remaining
    if command == "dumpdb" and file_arg is not None:
        raise MiniDoitError("dumpdb does not accept --file")
    if remaining and remaining[0].startswith("-") and remaining[0] not in COMMANDS:
        raise MiniDoitError(f"unknown option: {remaining[0]}")
    return Options(command=command, rest=rest, task_file=task_file, db_file=db_file)


def load_config(cwd: Path) -> tuple[Path, Path]:
    task_file = Path("dodo.py")
    db_file = Path(".minidoit.db.json")
    config = cwd / "pyproject.toml"
    if not config.exists():
        return task_file, db_file
    if tomllib is None:
        raise MiniDoitError("tomllib is required to read pyproject.toml")
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except Exception as exc:
        raise MiniDoitError(f"malformed config: {exc}") from exc
    section = data.get("tool", {}).get("minidoit", {})
    allowed = {"task_file", "db_file"}
    unknown = set(section) - allowed
    if unknown:
        raise MiniDoitError(f"unsupported config key: {sorted(unknown)[0]}")
    if "task_file" in section:
        task_file = Path(section["task_file"])
    if "db_file" in section:
        db_file = Path(section["db_file"])
    return task_file, db_file


def load_tasks(task_file: Path) -> dict[str, Task]:
    if not task_file.exists():
        raise MiniDoitError(f"missing task file: {task_file}")
    try:
        tree = ast.parse(task_file.read_text(encoding="utf-8"), filename=str(task_file))
    except SyntaxError as exc:
        raise MiniDoitError(f"malformed task file: {exc}") from exc

    tasks: dict[str, Task] = {}
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("task_"):
            raise MiniDoitError("task file may contain only task_<name>() functions")
        if node.decorator_list or node.args.args or node.args.kwonlyargs or node.args.vararg or node.args.kwarg:
            raise MiniDoitError(f"invalid task function: {node.name}")
        name = node.name.removeprefix("task_")
        if not name or not NAME_RE.match(name) or "=" in name:
            raise MiniDoitError(f"invalid task name: {name}")
        if name in tasks:
            raise MiniDoitError(f"duplicate task name: {name}")
        body = list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        if len(body) != 1 or not isinstance(body[0], ast.Return):
            raise MiniDoitError(f"task {name} must return one static task dictionary")
        try:
            raw = ast.literal_eval(body[0].value)
        except Exception as exc:
            raise MiniDoitError(f"task {name} must return static literals") from exc
        tasks[name] = task_from_dict(name, raw)
    return dict(sorted(tasks.items()))


def task_from_dict(name: str, raw: Any) -> Task:
    if not isinstance(raw, dict):
        raise MiniDoitError(f"task {name} must return a dictionary")
    unknown = set(raw) - ALLOWED_FIELDS
    if unknown:
        raise MiniDoitError(f"unsupported task field: {sorted(unknown)[0]}")
    if "actions" not in raw:
        raise MiniDoitError(f"task {name} missing actions")
    actions = require_str_list(raw["actions"], f"{name}.actions")
    file_dep = require_str_list(raw.get("file_dep", []), f"{name}.file_dep")
    targets = require_str_list(raw.get("targets", []), f"{name}.targets")
    task_dep = require_str_list(raw.get("task_dep", []), f"{name}.task_dep")
    for rel in file_dep + targets:
        validate_path(rel)
    for action in actions:
        validate_action(action)
    clean = raw.get("clean", False)
    validate_clean(clean)
    return Task(
        name=name,
        actions=actions,
        file_dep=file_dep,
        targets=targets,
        task_dep=task_dep,
        clean=clean,
        uptodate=raw.get("uptodate"),
        doc=str(raw.get("doc", "")),
        verbosity=raw.get("verbosity"),
    )


def require_str_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise MiniDoitError(f"{label} must be a list of strings")
    return list(value)


def validate_path(rel: str) -> None:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or rel == "":
        raise MiniDoitError(f"invalid path: {rel}")


def validate_action(action: str) -> None:
    if not isinstance(action, str) or not action.strip():
        raise MiniDoitError("invalid action")
    parts = action.split()
    keyword = parts[0]
    if keyword in {"write", "append"}:
        if len(parts) < 3:
            raise MiniDoitError(f"{keyword} requires path and text")
        validate_path(parts[1])
    elif keyword == "copy":
        if len(parts) != 3:
            raise MiniDoitError("copy requires source and destination")
        validate_path(parts[1])
        validate_path(parts[2])
    elif keyword == "delete":
        if len(parts) != 2:
            raise MiniDoitError("delete requires path")
        validate_path(parts[1])
    elif keyword == "fail":
        if len(parts) < 2:
            raise MiniDoitError("fail requires message")
    else:
        raise MiniDoitError(f"unsupported action: {keyword}")


def validate_clean(clean: Any) -> None:
    if clean in (False, True, None):
        return
    if isinstance(clean, list):
        for item in clean:
            if not isinstance(item, str):
                raise MiniDoitError("clean list entries must be strings")
            parts = item.split()
            if parts and parts[0] in {"write", "append", "copy", "delete", "fail"}:
                validate_action(item)
            else:
                validate_path(item)
        return
    raise MiniDoitError("invalid clean value")


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "tasks": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise MiniDoitError(f"invalid_state: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("tasks"), dict):
        raise MiniDoitError("invalid_state")
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def content_signature(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task_status(task: Task, state: dict[str, Any], completed: set[str] | None = None) -> tuple[str, list[str]]:
    completed = completed or set()
    entry = state.get("tasks", {}).get(task.name)
    reasons: list[str] = []
    if not entry or entry.get("status") != "success":
        reasons.append("no_success_state")
    for dep in task.file_dep:
        dep_path = Path(dep)
        if not dep_path.exists():
            reasons.append("missing_file_dep")
        elif entry and entry.get("file_dep", {}).get(dep) != content_signature(dep_path):
            reasons.append("changed_file_dep")
    for target in task.targets:
        if not Path(target).exists():
            reasons.append("missing_target")
    if task.uptodate is False or (isinstance(task.uptodate, list) and False in task.uptodate):
        reasons.append("uptodate_false")
    for dep in task.task_dep:
        if dep not in completed:
            dep_entry = state.get("tasks", {}).get(dep)
            if not dep_entry or dep_entry.get("status") != "success":
                reasons.append("task_failed")
    if "missing_file_dep" in reasons:
        return "error", stable_reasons(reasons)
    if reasons:
        return "run", stable_reasons(reasons)
    return "up_to_date", []


def stable_reasons(reasons: list[str]) -> list[str]:
    order = [
        "no_success_state",
        "changed_file_dep",
        "missing_file_dep",
        "missing_target",
        "uptodate_false",
        "task_failed",
        "invalid_task",
        "invalid_state",
    ]
    seen = set(reasons)
    return [reason for reason in order if reason in seen]


def cmd_list(opts: Options, tasks: dict[str, Task]) -> int:
    want_json = "--json" in opts.rest
    want_status = "--status" in opts.rest
    state = load_state(opts.db_file)
    records = []
    for task in tasks.values():
        record = task_record(task)
        if want_status or want_json:
            record["status"] = task_status(task, state)[0]
        records.append(record)
    if want_json:
        print(json.dumps({"tasks": records}, sort_keys=True))
    else:
        for record in records:
            print(record["name"])
    return 0


def cmd_info(opts: Options, tasks: dict[str, Task]) -> int:
    want_json = "--json" in opts.rest
    names = [arg for arg in opts.rest if not arg.startswith("--")]
    if len(names) != 1:
        raise MiniDoitError("info requires exactly one task")
    name = names[0]
    if name not in tasks:
        raise MiniDoitError(f"unknown task: {name}")
    state = load_state(opts.db_file)
    task = tasks[name]
    status, reasons = task_status(task, state)
    record = task_record(task)
    record.update({"clean": task.clean, "status": status, "reasons": reasons})
    if want_json:
        print(json.dumps(record, sort_keys=True))
    else:
        print(f"{name}: {status}")
    return 0


def task_record(task: Task) -> dict[str, Any]:
    return {
        "name": task.name,
        "doc": task.doc,
        "file_dep": task.file_dep,
        "targets": task.targets,
        "task_dep": task.task_dep,
    }


def cmd_dumpdb(opts: Options) -> int:
    want_json = "--json" in opts.rest
    state = load_state(opts.db_file)
    if want_json:
        print(json.dumps(state, sort_keys=True))
    else:
        print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def cmd_run(opts: Options, tasks: dict[str, Task]) -> int:
    selected = [arg for arg in opts.rest if not arg.startswith("--")]
    if not selected:
        selected = list(tasks)
    for name in selected:
        if name not in tasks:
            raise MiniDoitError(f"unknown task: {name}")
    state = load_state(opts.db_file)
    completed: set[str] = set()
    visiting: set[str] = set()
    failed = False

    def run_one(name: str) -> bool:
        nonlocal failed
        if name in completed:
            return True
        if name in visiting:
            raise MiniDoitError(f"cyclic dependency: {name}")
        task = tasks[name]
        visiting.add(name)
        for dep in task.task_dep:
            if dep not in tasks:
                raise MiniDoitError(f"unknown dependency: {dep}")
            if not run_one(dep):
                print(f"failed {name}", file=sys.stderr)
                failed = True
                visiting.remove(name)
                return False
        visiting.remove(name)
        status, reasons = task_status(task, state, completed)
        if status == "up_to_date":
            print(f"skipped {name}")
            completed.add(name)
            return True
        if status == "error":
            print(f"failed {name}: {','.join(reasons)}", file=sys.stderr)
            failed = True
            return False
        try:
            execute_actions(task.actions)
        except MiniDoitError as exc:
            print(f"failed {name}: {exc}", file=sys.stderr)
            failed = True
            return False
        state.setdefault("tasks", {})[name] = {
            "status": "success",
            "file_dep": {dep: content_signature(Path(dep)) for dep in task.file_dep},
            "targets": task.targets,
            "last_result": "success",
        }
        save_state(opts.db_file, state)
        print(f"executed {name}")
        completed.add(name)
        return True

    for name in selected:
        run_one(name)
    return 1 if failed else 0


def execute_actions(actions: list[str]) -> None:
    for action in actions:
        parts = action.split()
        keyword = parts[0]
        if keyword == "write":
            path = Path(parts[1])
            text = " ".join(parts[2:])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        elif keyword == "append":
            path = Path(parts[1])
            text = " ".join(parts[2:])
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(text)
        elif keyword == "copy":
            src = Path(parts[1])
            dst = Path(parts[2])
            if not src.exists():
                raise MiniDoitError(f"missing source: {src}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        elif keyword == "delete":
            path = Path(parts[1])
            if path.exists():
                path.unlink()
        elif keyword == "fail":
            raise MiniDoitError(" ".join(parts[1:]))
        else:
            raise MiniDoitError(f"unsupported action: {keyword}")


def cmd_clean(opts: Options, tasks: dict[str, Task]) -> int:
    forget = "--forget" in opts.rest
    selected = [arg for arg in opts.rest if not arg.startswith("--")]
    if not selected:
        selected = list(tasks)
    for name in selected:
        if name not in tasks:
            raise MiniDoitError(f"unknown task: {name}")
    state = load_state(opts.db_file)
    for name in selected:
        clean_task(tasks[name])
        if forget:
            state.get("tasks", {}).pop(name, None)
    if forget:
        save_state(opts.db_file, state)
    return 0


def clean_task(task: Task) -> None:
    clean = task.clean
    if clean is True:
        for rel in task.targets:
            remove_file(rel)
    elif isinstance(clean, list):
        for item in clean:
            parts = item.split()
            if parts and parts[0] in {"write", "append", "copy", "delete", "fail"}:
                execute_actions([item])
            else:
                remove_file(item)


def remove_file(rel: str) -> None:
    path = Path(rel)
    if path.exists():
        path.unlink()


def cmd_forget(opts: Options, tasks: dict[str, Task]) -> int:
    all_tasks = "--all" in opts.rest
    selected = [arg for arg in opts.rest if not arg.startswith("--")]
    if not all_tasks:
        if not selected:
            raise MiniDoitError("forget requires TASK or --all")
        for name in selected:
            if name not in tasks:
                raise MiniDoitError(f"unknown task: {name}")
    state = load_state(opts.db_file)
    if all_tasks:
        state["tasks"] = {}
    else:
        for name in selected:
            state.get("tasks", {}).pop(name, None)
    save_state(opts.db_file, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

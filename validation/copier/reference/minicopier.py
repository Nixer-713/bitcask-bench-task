#!/usr/bin/env python3
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

import yaml


SETTINGS = {
    "_answers_file",
    "_templates_suffix",
    "_exclude",
    "_skip_if_exists",
    "_subdirectory",
    "_tasks",
    "_migrations",
    "_secret_questions",
}


def fail(msg):
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def posix(path):
    return Path(path).as_posix()


def load_yaml(path):
    try:
        data = yaml.safe_load(Path(path).read_text())
    except Exception as exc:
        fail(f"invalid yaml: {exc}")
    return data or {}


def dump_yaml(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def render_text(text, answers):
    def repl(match):
        return str(answers.get(match.group(1).strip(), ""))

    return re.sub(r"{{\s*([^{}]+?)\s*}}", repl, text)


def falsey(value):
    return str(value).strip() in {"", "false", "False", "0", "no"}


def is_git_repo(path):
    return (Path(path) / ".git").exists()


def git(args, cwd):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def semver_key(tag):
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    if not m:
        return None
    return tuple(map(int, m.groups()))


def newest_ref(repo):
    try:
        tags = git(["tag"], repo).splitlines()
    except Exception:
        tags = []
    semvers = [(semver_key(t), t) for t in tags if semver_key(t) is not None]
    if semvers:
        return max(semvers)[1]
    return "HEAD"


def checkout_tree(src, ref=None):
    src = Path(src)
    if not is_git_repo(src):
        return src, None
    selected = ref or newest_ref(src)
    tmp = Path(tempfile.mkdtemp(prefix="minicopier-template-"))
    names = git(["ls-tree", "-r", "--name-only", selected], src).splitlines()
    for name in names:
        out = tmp / name
        out.parent.mkdir(parents=True, exist_ok=True)
        data = subprocess.check_output(["git", "show", f"{selected}:{name}"], cwd=src)
        out.write_bytes(data)
    return tmp, selected


def config_path(tree):
    if (tree / "copier.yml").exists():
        return tree / "copier.yml"
    if (tree / "copier.yaml").exists():
        return tree / "copier.yaml"
    return None


def load_config(tree):
    cp = config_path(tree)
    if not cp:
        return {}
    data = load_yaml(cp)
    if not isinstance(data, dict):
        fail("invalid config")
    for key in ["_exclude", "_skip_if_exists", "_secret_questions", "_tasks"]:
        if key in data and not isinstance(data[key], list):
            fail(f"invalid {key}")
    if "_migrations" in data and not isinstance(data["_migrations"], list):
        fail("invalid _migrations")
    return data


def parse_data_items(items):
    data = {}
    for item in items or []:
        if "=" not in item:
            fail("data must be KEY=VALUE")
        k, v = item.split("=", 1)
        data[k] = v
    return data


def question_defaults(config, base_answers=None):
    answers = dict(base_answers or {})
    skipped = set()
    for key, val in config.items():
        if key.startswith("_"):
            continue
        secret = False
        when = None
        default = val
        if isinstance(val, dict):
            default = val.get("default", "")
            secret = bool(val.get("secret"))
            when = val.get("when")
        if when is not None and falsey(render_text(str(when), answers)):
            skipped.add(key)
            continue
        answers.setdefault(key, default)
    return answers, skipped


def read_answers(path):
    if not Path(path).exists():
        fail("answers file missing")
    data = load_yaml(path)
    if not isinstance(data, dict):
        fail("invalid answers")
    return data


def answers_file_for(dest, config=None, override=None, existing_required=False):
    if override:
        return Path(dest) / override
    default = Path(dest) / ".copier-answers.yml"
    if existing_required:
        return default
    af = (config or {}).get("_answers_file", ".copier-answers.yml")
    return Path(dest) / af


def match_pat(path, pat):
    path = posix(path)
    if pat.endswith("/"):
        return path == pat[:-1] or path.startswith(pat)
    return fnmatch.fnmatch(path, pat)


def any_match(path, patterns):
    return any(match_pat(path, pat) for pat in patterns)


def source_root(tree, config):
    sub = config.get("_subdirectory")
    root = tree / sub if sub else tree
    if not root.exists():
        fail("missing subdirectory")
    return root


def rendered_files(tree, config, answers, extra_exclude=None, extra_skip=None):
    suffix = config.get("_templates_suffix", ".jinja")
    excludes = list(config.get("_exclude", []) or []) + list(extra_exclude or [])
    skips = list(config.get("_skip_if_exists", []) or []) + list(extra_skip or [])
    root = source_root(tree, config)
    files = {}
    excluded = []
    for src in sorted(p for p in root.rglob("*") if p.is_file()):
        rel_src = src.relative_to(root)
        if ".git" in rel_src.parts:
            continue
        if not config.get("_subdirectory") and rel_src.as_posix() in {"copier.yml", "copier.yaml"}:
            continue
        parts = [render_text(part, answers) for part in rel_src.parts]
        if any(part == "" for part in parts):
            continue
        rel = PurePosixPath(*parts).as_posix()
        do_render = rel.endswith(suffix)
        if do_render:
            rel = rel[: -len(suffix)]
        if any_match(rel, excludes):
            excluded.append(rel)
            continue
        text = src.read_text(encoding="utf-8")
        files[rel] = render_text(text, answers) if do_render else text
    return files, excluded, skips


def plan_apply(dest, files, answers_path=None, answers=None, overwrite=False, skip_patterns=None):
    dest = Path(dest)
    skip_patterns = list(skip_patterns or [])
    writes = {}
    skipped = []
    for rel, text in files.items():
        out = dest / rel
        if out.exists() and any_match(rel, skip_patterns):
            skipped.append(rel)
            continue
        if out.exists() and not overwrite:
            fail(f"refusing to overwrite {rel}")
        writes[rel] = text
    if answers_path and answers is not None:
        writes[posix(Path(answers_path).relative_to(dest))] = yaml.safe_dump(answers, sort_keys=False)
    return writes, skipped


def apply_writes(dest, writes):
    dest = Path(dest)
    for rel, text in writes.items():
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")


def selected_answers_for_copy(config, data_file, data_items):
    defaults, skipped = question_defaults(config)
    answers = dict(defaults)
    if data_file:
        df = load_yaml(data_file)
        if not isinstance(df, dict):
            fail("invalid data file")
        answers.update(df)
    answers.update(parse_data_items(data_items))
    for key in skipped:
        answers.pop(key, None)
    return answers


def selected_answers_for_existing(config, previous, data_items):
    defaults, skipped = question_defaults(config)
    answers = dict(defaults)
    answers.update({k: v for k, v in previous.items() if not k.startswith("_")})
    answers.update(parse_data_items(data_items))
    for key in skipped:
        answers.pop(key, None)
    return answers


def stored_answers(config, answers, src_path, commit):
    secret = set(config.get("_secret_questions", []) or [])
    for k, v in config.items():
        if isinstance(v, dict) and v.get("secret"):
            secret.add(k)
    out = {"_src_path": src_path}
    if commit is not None:
        out["_commit"] = commit
    for k, v in answers.items():
        if k not in secret and not k.startswith("_"):
            out[k] = v
    return out


def safe_actions(actions, dest):
    for action in actions or []:
        parts = str(action).split(" ", 2)
        if len(parts) < 3 or parts[0] not in {"write", "append"}:
            fail("unsupported safe action")
        op, rel, text = parts
        path = Path(dest) / rel
        if ".." in Path(rel).parts or Path(rel).is_absolute():
            fail("unsafe action path")
        path.parent.mkdir(parents=True, exist_ok=True)
        if op == "write":
            path.write_text(text, encoding="utf-8")
        else:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")


def check_unsafe(config, trust, skip_tasks, is_update=False):
    if config.get("_tasks") and not trust and not skip_tasks:
        fail("tasks require trust")
    if is_update and config.get("_migrations") and not trust:
        fail("migrations require trust")


def command_copy(args):
    if "://" in args.template:
        fail("remote templates unsupported")
    tree, commit = checkout_tree(args.template, args.vcs_ref)
    config = load_config(tree)
    check_unsafe(config, args.trust, args.skip_tasks)
    answers = selected_answers_for_copy(config, args.data_file, args.data)
    files, excluded, skip_patterns = rendered_files(tree, config, answers, args.exclude, args.skip)
    dest = Path(args.dest)
    af = answers_file_for(dest, config, args.answers_file)
    stored = stored_answers(config, answers, args.template, commit)
    writes, skipped = plan_apply(dest, files, af, stored, args.overwrite, skip_patterns)
    if args.pretend:
        print(json.dumps({"ok": True, "command": "copy", "operation": "copy", "pretend": True, "written": sorted(writes), "skipped": skipped, "excluded": excluded}))
        return
    created_new = not dest.exists()
    old_snapshot = snapshot(dest) if dest.exists() else None
    try:
        apply_writes(dest, writes)
        if config.get("_tasks") and not args.skip_tasks:
            safe_actions(config.get("_tasks"), dest)
    except Exception:
        restore(dest, old_snapshot, remove_if_missing=created_new)
        raise
    print(json.dumps({"ok": True, "command": "copy", "operation": "copy", "answers_file": posix(af.relative_to(dest)), "commit": commit, "written": sorted(writes), "skipped": skipped, "excluded": excluded}))


def snapshot(path):
    path = Path(path)
    if not path.exists():
        return None
    tmp = Path(tempfile.mkdtemp(prefix="minicopier-snapshot-"))
    shutil.copytree(path, tmp / "tree", dirs_exist_ok=True)
    return tmp / "tree"


def restore(path, snap, remove_if_missing=False):
    path = Path(path)
    if path.exists():
        shutil.rmtree(path)
    if snap is not None:
        shutil.copytree(snap, path)
    elif remove_if_missing:
        shutil.rmtree(path, ignore_errors=True)


def existing_context(dest, answers_file=None):
    af = answers_file_for(dest, override=answers_file, existing_required=True)
    prev = read_answers(af)
    src = prev.get("_src_path")
    if not src:
        fail("missing _src_path")
    return af, prev, src


def command_check_update(args):
    af, prev, src = existing_context(args.dest, args.answers_file)
    current = prev.get("_commit")
    latest = newest_ref(src) if is_git_repo(src) else current
    print(json.dumps({"ok": True, "command": "check-update", "current": current, "latest": latest, "update_available": bool(latest and latest != current)}))


def command_recopy(args):
    af, prev, src = existing_context(args.dest, args.answers_file)
    tree, commit = checkout_tree(src, prev.get("_commit"))
    config = load_config(tree)
    answers = selected_answers_for_existing(config, prev, args.data)
    files, excluded, skip_patterns = rendered_files(tree, config, answers, args.exclude, args.skip)
    stored = stored_answers(config, answers, src, commit)
    writes, skipped = plan_apply(args.dest, files, af, stored, args.overwrite, skip_patterns)
    if args.pretend:
        print(json.dumps({"ok": True, "command": "recopy", "operation": "recopy", "pretend": True, "written": sorted(writes), "skipped": skipped, "excluded": excluded}))
        return
    snap = snapshot(args.dest)
    try:
        apply_writes(args.dest, writes)
        if config.get("_tasks"):
            safe_actions(config.get("_tasks"), args.dest)
    except Exception:
        restore(args.dest, snap)
        raise
    print(json.dumps({"ok": True, "command": "recopy", "operation": "recopy", "written": sorted(writes), "skipped": skipped, "excluded": excluded}))


def migration_actions(config, phase):
    actions = []
    for mig in config.get("_migrations", []) or []:
        if isinstance(mig, dict):
            actions.extend(mig.get(phase, []) or [])
    return actions


def command_update(args):
    af, prev, src = existing_context(args.dest, args.answers_file)
    old_ref = prev.get("_commit")
    if not is_git_repo(src):
        fail("update requires git template")
    new_ref = args.vcs_ref or newest_ref(src)
    old_tree, _ = checkout_tree(src, old_ref)
    new_tree, commit = checkout_tree(src, new_ref)
    old_config = load_config(old_tree)
    new_config = load_config(new_tree)
    check_unsafe(new_config, args.trust, args.skip_tasks, is_update=True)
    answers = selected_answers_for_existing(new_config, prev, args.data)
    old_files, _, _ = rendered_files(old_tree, old_config, answers, args.exclude, args.skip)
    new_files, excluded, skip_patterns = rendered_files(new_tree, new_config, answers, args.exclude, args.skip)
    dest = Path(args.dest)
    stored = stored_answers(new_config, answers, src, commit)
    writes = {}
    skipped = []
    conflicts = []
    for rel, new_text in new_files.items():
        out = dest / rel
        if out.exists() and any_match(rel, skip_patterns):
            skipped.append(rel)
            continue
        old_text = old_files.get(rel, "")
        current = out.read_text(encoding="utf-8") if out.exists() else old_text
        if current == new_text:
            continue
        if current == old_text or not out.exists():
            writes[rel] = new_text
        else:
            conflicts.append(rel)
            if args.conflict == "inline":
                writes[rel] = f"<<<<<<< local\n{current}=======\n{new_text}>>>>>>> template\n"
            else:
                writes[rel + ".rej"] = new_text
    writes[posix(af.relative_to(dest))] = yaml.safe_dump(stored, sort_keys=False)
    if args.pretend:
        print(json.dumps({"ok": True, "command": "update", "operation": "update", "pretend": True, "written": sorted(writes), "skipped": skipped, "excluded": excluded, "conflicts": conflicts}))
        return
    snap = snapshot(dest)
    try:
        if new_config.get("_migrations"):
            safe_actions(migration_actions(new_config, "before"), dest)
        apply_writes(dest, writes)
        if new_config.get("_migrations"):
            safe_actions(migration_actions(new_config, "after"), dest)
        if new_config.get("_tasks") and not args.skip_tasks:
            safe_actions(new_config.get("_tasks"), dest)
    except Exception:
        restore(dest, snap)
        raise
    print(json.dumps({"ok": True, "command": "update", "operation": "update", "commit": commit, "written": sorted(writes), "skipped": skipped, "excluded": excluded, "conflicts": conflicts}))


def build_parser():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    cp = sub.add_parser("copy")
    cp.add_argument("template")
    cp.add_argument("dest")
    cp.add_argument("--answers-file")
    cp.add_argument("--data", action="append")
    cp.add_argument("--data-file")
    cp.add_argument("--defaults", action="store_true")
    cp.add_argument("--overwrite", action="store_true")
    cp.add_argument("--exclude", action="append")
    cp.add_argument("--skip", action="append")
    cp.add_argument("--vcs-ref")
    cp.add_argument("--pretend", action="store_true")
    cp.add_argument("--trust", action="store_true")
    cp.add_argument("--skip-tasks", action="store_true")

    rp = sub.add_parser("recopy")
    rp.add_argument("dest")
    rp.add_argument("--answers-file")
    rp.add_argument("--data", action="append")
    rp.add_argument("--overwrite", action="store_true")
    rp.add_argument("--skip-answered", action="store_true")
    rp.add_argument("--exclude", action="append")
    rp.add_argument("--skip", action="append")
    rp.add_argument("--pretend", action="store_true")

    up = sub.add_parser("update")
    up.add_argument("dest")
    up.add_argument("--answers-file")
    up.add_argument("--vcs-ref")
    up.add_argument("--data", action="append")
    up.add_argument("--overwrite", action="store_true")
    up.add_argument("--skip-answered", action="store_true")
    up.add_argument("--exclude", action="append")
    up.add_argument("--skip", action="append")
    up.add_argument("--conflict", choices=["inline", "rej"], default="rej")
    up.add_argument("--pretend", action="store_true")
    up.add_argument("--trust", action="store_true")
    up.add_argument("--skip-tasks", action="store_true")

    chk = sub.add_parser("check-update")
    chk.add_argument("dest")
    chk.add_argument("--answers-file")
    chk.add_argument("--json", action="store_true")
    return p


def main():
    args = build_parser().parse_args()
    try:
        if args.cmd == "copy":
            command_copy(args)
        elif args.cmd == "recopy":
            command_recopy(args)
        elif args.cmd == "update":
            command_update(args)
        elif args.cmd == "check-update":
            command_check_update(args)
    except SystemExit:
        raise
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()

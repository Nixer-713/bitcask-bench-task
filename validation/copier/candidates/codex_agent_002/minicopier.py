#!/usr/bin/env python3
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

try:
    import yaml
except Exception:  # pragma: no cover - fallback for very small environments
    yaml = None


DEFAULT_ANSWERS = ".copier-answers.yml"
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
VAR_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")


class MiniCopierError(Exception):
    pass


def fail(message):
    print(message, file=sys.stderr)
    return 1


def load_yaml_text(text, source):
    if not text.strip():
        return {}
    if yaml is not None:
        try:
            data = yaml.safe_load(text)
        except Exception as exc:
            raise MiniCopierError(f"malformed YAML in {source}: {exc}") from exc
        return {} if data is None else data
    return parse_simple_yaml(text, source)


def parse_simple_yaml(text, source):
    """A small YAML subset reader used only when PyYAML is unavailable."""
    root = {}
    stack = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            if not isinstance(parent, list):
                raise MiniCopierError(f"malformed YAML in {source}")
            item = parse_scalar(line[2:])
            parent.append(item)
            continue
        if ":" not in line:
            raise MiniCopierError(f"malformed YAML in {source}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            nxt = {}
            parent[key] = nxt
            stack.append((indent, nxt))
        else:
            parent[key] = parse_scalar(value)
    return root


def parse_scalar(value):
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if value in ("null", "None", "~"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    return value


def dump_yaml(data):
    if yaml is not None:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    lines = []
    for key, value in data.items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def read_yaml_file(path):
    try:
        return load_yaml_text(Path(path).read_text(encoding="utf-8"), str(path))
    except OSError as exc:
        raise MiniCopierError(f"cannot read {path}: {exc}") from exc


def parse_key_values(items):
    data = {}
    for item in items or []:
        if "=" not in item:
            raise MiniCopierError(f"invalid --data value {item!r}; expected KEY=VALUE")
        key, value = item.split("=", 1)
        if not key:
            raise MiniCopierError("invalid --data key")
        data[key] = value
    return data


def as_list(value, setting):
    if value is None:
        return []
    if not isinstance(value, list):
        raise MiniCopierError(f"{setting} must be a list")
    return value


def as_str(value, setting):
    if value is None:
        return None
    if not isinstance(value, str):
        raise MiniCopierError(f"{setting} must be a string")
    return value


def is_remote_source(src):
    return "://" in src or src.startswith("git@") or re.match(r"^[A-Za-z0-9_.-]+:[^/]", src)


def git(cwd, *args):
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise MiniCopierError(proc.stderr.strip() or "git command failed")
    return proc.stdout


def semver_key(tag):
    match = SEMVER_RE.match(tag)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def newest_semver_tag(repo):
    tags = [line.strip() for line in git(repo, "tag", "--list").splitlines() if line.strip()]
    semvers = [(semver_key(tag), tag) for tag in tags if semver_key(tag) is not None]
    if not semvers:
        return None
    semvers.sort(key=lambda item: item[0])
    return semvers[-1][1]


class Template:
    def __init__(self, source, ref=None):
        if is_remote_source(source):
            raise MiniCopierError("remote template sources are unsupported")
        self.path = Path(source).resolve()
        if not self.path.exists():
            raise MiniCopierError(f"template not found: {source}")
        self.is_git = (self.path / ".git").exists()
        self.ref = None
        self.commit = None
        if self.is_git:
            self.ref, self.commit = self.select_ref(ref)
        elif ref:
            raise MiniCopierError("--vcs-ref requires a local Git template")

    def select_ref(self, requested):
        if requested:
            try:
                git(self.path, "rev-parse", "--verify", f"{requested}^{{tree}}")
            except MiniCopierError as exc:
                raise MiniCopierError(f"unsupported local Git ref: {requested}") from exc
            return requested, requested
        tag = newest_semver_tag(self.path)
        if tag:
            return tag, tag
        git(self.path, "rev-parse", "--verify", "HEAD^{tree}")
        return "HEAD", "HEAD"

    def read_text(self, relpath):
        rel = str(PurePosixPath(relpath))
        if self.is_git:
            try:
                return git(self.path, "show", f"{self.ref}:{rel}")
            except MiniCopierError as exc:
                raise FileNotFoundError(rel) from exc
        return (self.path / rel).read_text(encoding="utf-8")

    def exists(self, relpath):
        rel = str(PurePosixPath(relpath))
        if self.is_git:
            proc = subprocess.run(
                ["git", "cat-file", "-e", f"{self.ref}:{rel}"],
                cwd=str(self.path),
                text=True,
                capture_output=True,
            )
            return proc.returncode == 0
        return (self.path / rel).exists()

    def list_files(self, subdir=""):
        prefix = str(PurePosixPath(subdir)) if subdir else ""
        if prefix == ".":
            prefix = ""
        if self.is_git:
            args = ["ls-tree", "-r", "-z", "--name-only", self.ref]
            if prefix:
                args.extend(["--", prefix])
            out = subprocess.run(
                ["git", *args],
                cwd=str(self.path),
                capture_output=True,
            )
            if out.returncode != 0:
                raise MiniCopierError(out.stderr.decode("utf-8", "replace").strip())
            names = [p.decode("utf-8") for p in out.stdout.split(b"\0") if p]
            return [str(PurePosixPath(name)) for name in names]
        base = self.path / prefix
        if not base.exists():
            raise MiniCopierError(f"template subdirectory not found: {prefix}")
        files = []
        for root, dirs, names in os.walk(base):
            dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
            for name in names:
                path = Path(root) / name
                if path.is_symlink():
                    continue
                files.append(path.relative_to(self.path).as_posix())
        return files


def load_config(template):
    config_name = None
    if template.exists("copier.yml"):
        config_name = "copier.yml"
    elif template.exists("copier.yaml"):
        config_name = "copier.yaml"
    if config_name is None:
        config = {}
    else:
        config = load_yaml_text(template.read_text(config_name), config_name)
    if not isinstance(config, dict):
        raise MiniCopierError("template config must be a mapping")
    settings = {
        "_answers_file": DEFAULT_ANSWERS,
        "_templates_suffix": ".jinja",
        "_exclude": [],
        "_skip_if_exists": [],
        "_subdirectory": "",
        "_tasks": [],
        "_migrations": [],
        "_secret_questions": [],
    }
    if "_answers_file" in config:
        settings["_answers_file"] = as_str(config.get("_answers_file"), "_answers_file")
    if "_templates_suffix" in config:
        settings["_templates_suffix"] = as_str(config.get("_templates_suffix"), "_templates_suffix")
    if "_subdirectory" in config:
        settings["_subdirectory"] = as_str(config.get("_subdirectory"), "_subdirectory") or ""
    for key in ("_exclude", "_skip_if_exists", "_tasks", "_migrations", "_secret_questions"):
        if key in config:
            settings[key] = as_list(config.get(key), key)
    return config, settings


def render_text(text, answers):
    def repl(match):
        value = answers.get(match.group(1), "")
        return "" if value is None else str(value)

    return VAR_RE.sub(repl, text)


def falsey_rendered(value):
    return value.strip() in ("", "false", "False", "0", "no")


def question_defaults(config, base_answers=None):
    answers = dict(base_answers or {})
    defaults = {}
    skipped = set()
    secrets = set(as_list(config.get("_secret_questions", []), "_secret_questions"))
    for key, value in config.items():
        if key.startswith("_"):
            continue
        secret = False
        when = None
        if isinstance(value, dict):
            default = value.get("default", "")
            secret = bool(value.get("secret", False))
            when = value.get("when")
        else:
            default = value
        if secret:
            secrets.add(key)
        candidate_answers = dict(answers)
        candidate_answers.setdefault(key, default)
        if when is not None and falsey_rendered(render_text(str(when), candidate_answers)):
            skipped.add(key)
            answers.pop(key, None)
            continue
        if key not in answers:
            answers[key] = default
        defaults[key] = answers[key]
    return defaults, skipped, secrets


def resolve_answers(config, sources):
    merged = {}
    defaults, skipped, secrets = question_defaults(config, merged)
    merged.update(defaults)
    for source in sources:
        merged.update(source)
    _, skipped, secrets = question_defaults(config, merged)
    for key in skipped:
        merged.pop(key, None)
    return merged, skipped, secrets


def match_pattern(path, pattern):
    path = path.strip("/")
    pattern = pattern.strip()
    if pattern.endswith("/"):
        prefix = pattern.strip("/")
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatch(path, pattern)


def any_match(path, patterns):
    return any(match_pattern(path, str(pattern)) for pattern in patterns)


def render_relpath(template_rel, subdir, suffix, answers):
    rel = PurePosixPath(template_rel)
    if subdir:
        rel = rel.relative_to(PurePosixPath(subdir))
    parts = []
    for part in rel.parts:
        rendered = render_text(part, answers)
        if rendered == "":
            return None
        parts.append(rendered)
    dest = str(PurePosixPath(*parts))
    if dest.endswith(suffix):
        dest = dest[: -len(suffix)]
    return dest


def render_plan(template, config, settings, answers, cli_exclude, cli_skip):
    subdir = settings["_subdirectory"] or ""
    files = template.list_files(subdir)
    suffix = settings["_templates_suffix"]
    exclude = [str(p) for p in settings["_exclude"] + (cli_exclude or [])]
    skip = [str(p) for p in settings["_skip_if_exists"] + (cli_skip or [])]
    writes = {}
    excluded = []
    for rel in files:
        root_rel = str(PurePosixPath(rel))
        if not subdir and root_rel in ("copier.yml", "copier.yaml"):
            continue
        dest_rel = render_relpath(root_rel, subdir, suffix, answers)
        if not dest_rel:
            continue
        if any_match(dest_rel, exclude):
            excluded.append(dest_rel)
            continue
        content = template.read_text(root_rel)
        if root_rel.endswith(suffix):
            content = render_text(content, answers)
        writes[dest_rel] = content
    return writes, sorted(set(excluded)), skip


def safe_dest_path(dest, relpath):
    rel = PurePosixPath(relpath)
    if rel.is_absolute() or ".." in rel.parts:
        raise MiniCopierError(f"unsafe destination path: {relpath}")
    path = (Path(dest) / Path(*rel.parts)).resolve()
    dest_resolved = Path(dest).resolve()
    if dest_resolved != path and dest_resolved not in path.parents:
        raise MiniCopierError(f"unsafe destination path: {relpath}")
    return path


def apply_writes(dest, writes):
    written = []
    for rel, content in writes.items():
        path = safe_dest_path(dest, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)
    return sorted(written)


def remove_empty_created_dest(dest, existed_before):
    if not existed_before and Path(dest).exists():
        shutil.rmtree(dest)


def answers_payload(template, commit, answers, skipped, secrets):
    payload = {"_src_path": str(template.path)}
    if commit:
        payload["_commit"] = commit
    for key, value in answers.items():
        if key.startswith("_") or key in skipped or key in secrets:
            continue
        payload[key] = value
    return payload


def write_answers_file(dest, answers_file, payload):
    rel = str(PurePosixPath(answers_file))
    path = safe_dest_path(dest, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(payload), encoding="utf-8")
    return rel


def load_answers(dest, answers_file):
    path = safe_dest_path(dest, answers_file)
    if not path.exists():
        raise MiniCopierError(f"destination answers file missing: {answers_file}")
    data = read_yaml_file(path)
    if not isinstance(data, dict):
        raise MiniCopierError("answers file must be a mapping")
    return data


def validate_actions(actions):
    parsed = []
    for action in actions:
        if not isinstance(action, str):
            raise MiniCopierError("safe actions must be strings")
        parts = action.split(" ", 2)
        if len(parts) != 3 or parts[0] not in ("write", "append"):
            raise MiniCopierError(f"unsupported safe action: {action}")
        parsed.append(tuple(parts))
    return parsed


def preflight_actions(dest, actions):
    parsed = validate_actions(actions)
    for _, rel, _ in parsed:
        safe_dest_path(dest, rel)
    return parsed


def apply_actions(dest, actions):
    for op, rel, text in validate_actions(actions):
        path = safe_dest_path(dest, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        if op == "write":
            path.write_text(text, encoding="utf-8")
        else:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")


def migration_actions(migrations, phase):
    actions = []
    for migration in migrations:
        if not isinstance(migration, dict):
            raise MiniCopierError("migrations must be mappings")
        actions.extend(as_list(migration.get(phase, []), f"migration {phase}"))
    return actions


def precheck_overwrite(dest, writes, skip_patterns, overwrite, force=False):
    skipped = []
    planned = {}
    for rel, content in writes.items():
        path = safe_dest_path(dest, rel)
        if path.exists() and any_match(rel, skip_patterns):
            skipped.append(rel)
            continue
        if path.exists() and not overwrite and not force:
            raise MiniCopierError(f"destination file exists; use --overwrite: {rel}")
        planned[rel] = content
    return planned, sorted(skipped)


def command_copy(args):
    template = Template(args.template, args.vcs_ref)
    config, settings = load_config(template)
    data_file = read_yaml_file(args.data_file) if args.data_file else {}
    if not isinstance(data_file, dict):
        raise MiniCopierError("--data-file must contain a mapping")
    answers, skipped_questions, secrets = resolve_answers(
        config, [data_file, parse_key_values(args.data)]
    )
    if settings["_tasks"] and not (args.trust or args.skip_tasks):
        raise MiniCopierError("template tasks require --trust or --skip-tasks")
    if settings["_tasks"] and not args.skip_tasks:
        preflight_actions(args.dest, settings["_tasks"])
    writes, excluded, skip_patterns = render_plan(
        template, config, settings, answers, args.exclude, args.skip
    )
    planned, skipped = precheck_overwrite(args.dest, writes, skip_patterns, args.overwrite)
    answers_file = args.answers_file or settings["_answers_file"] or DEFAULT_ANSWERS
    payload = answers_payload(template, template.commit, answers, skipped_questions, secrets)
    if args.pretend:
        return {
            "ok": True,
            "command": "copy",
            "operation": "copy",
            "pretend": True,
            "answers_file": answers_file,
            "commit": template.commit,
            "written": sorted(planned),
            "skipped": skipped,
            "excluded": excluded,
        }
    dest = Path(args.dest)
    existed = dest.exists()
    try:
        dest.mkdir(parents=True, exist_ok=True)
        written = apply_writes(dest, planned)
        write_answers_file(dest, answers_file, payload)
        if settings["_tasks"] and not args.skip_tasks:
            apply_actions(dest, settings["_tasks"])
    except Exception:
        remove_empty_created_dest(dest, existed)
        raise
    return {
        "ok": True,
        "command": "copy",
        "operation": "copy",
        "answers_file": answers_file,
        "commit": template.commit,
        "written": written,
        "skipped": skipped,
        "excluded": excluded,
    }


def template_from_answers(existing, ref_override=None):
    src = existing.get("_src_path")
    if not src:
        raise MiniCopierError("answers file lacks _src_path")
    ref = ref_override
    if ref is None:
        ref = existing.get("_commit")
    return Template(src, ref)


def command_recopy(args):
    answers_file = args.answers_file or DEFAULT_ANSWERS
    existing = load_answers(args.dest, answers_file)
    template = template_from_answers(existing)
    config, settings = load_config(template)
    prior = {k: v for k, v in existing.items() if not k.startswith("_")}
    overrides = parse_key_values(args.data)
    answers, skipped_questions, secrets = resolve_answers(config, [prior, overrides])
    if settings["_tasks"] and not args.skip_tasks:
        preflight_actions(args.dest, settings["_tasks"])
    if settings["_tasks"] and not (args.skip_tasks or args.pretend):
        raise MiniCopierError("template tasks require --trust")
    writes, excluded, skip_patterns = render_plan(
        template, config, settings, answers, args.exclude, args.skip
    )
    planned, skipped = precheck_overwrite(
        args.dest, writes, skip_patterns, overwrite=True, force=True
    )
    if args.pretend:
        return {
            "ok": True,
            "command": "recopy",
            "operation": "recopy",
            "pretend": True,
            "answers_file": answers_file,
            "commit": template.commit,
            "written": sorted(planned),
            "skipped": skipped,
            "excluded": excluded,
        }
    written = apply_writes(args.dest, planned)
    payload = answers_payload(template, template.commit, answers, skipped_questions, secrets)
    write_answers_file(args.dest, answers_file, payload)
    if settings["_tasks"] and not args.skip_tasks:
        apply_actions(args.dest, settings["_tasks"])
    return {
        "ok": True,
        "command": "recopy",
        "operation": "recopy",
        "answers_file": answers_file,
        "commit": template.commit,
        "written": written,
        "skipped": skipped,
        "excluded": excluded,
    }


def command_check_update(args):
    answers_file = args.answers_file or DEFAULT_ANSWERS
    existing = load_answers(args.dest, answers_file)
    src = existing.get("_src_path")
    if not src:
        raise MiniCopierError("answers file lacks _src_path")
    template = Template(src)
    latest = template.commit
    current = existing.get("_commit")
    return {
        "ok": True,
        "command": "check-update",
        "current": current,
        "latest": latest,
        "update_available": current != latest,
    }


def command_update(args):
    answers_file = args.answers_file or DEFAULT_ANSWERS
    existing = load_answers(args.dest, answers_file)
    src = existing.get("_src_path")
    old_commit = existing.get("_commit")
    if not src:
        raise MiniCopierError("answers file lacks _src_path")
    old_template = Template(src, old_commit) if old_commit else Template(src)
    new_template = Template(src, args.vcs_ref)
    old_config, old_settings = load_config(old_template)
    new_config, new_settings = load_config(new_template)
    prior = {k: v for k, v in existing.items() if not k.startswith("_")}
    answers, skipped_questions, secrets = resolve_answers(
        new_config, [prior, parse_key_values(args.data)]
    )
    if new_settings["_migrations"] and not args.trust:
        raise MiniCopierError("template migrations require --trust")
    if new_settings["_tasks"] and not (args.trust or args.skip_tasks):
        raise MiniCopierError("template tasks require --trust or --skip-tasks")
    before_actions = migration_actions(new_settings["_migrations"], "before")
    after_actions = migration_actions(new_settings["_migrations"], "after")
    if args.trust:
        preflight_actions(args.dest, before_actions + after_actions)
    if new_settings["_tasks"] and not args.skip_tasks:
        preflight_actions(args.dest, new_settings["_tasks"])
    old_writes, _, _ = render_plan(old_template, old_config, old_settings, answers, [], [])
    new_writes, excluded, skip_patterns = render_plan(
        new_template, new_config, new_settings, answers, args.exclude, args.skip
    )
    planned = {}
    skipped = []
    conflicts = []
    reject_writes = {}
    for rel, new_content in new_writes.items():
        path = safe_dest_path(args.dest, rel)
        if path.exists() and any_match(rel, skip_patterns):
            skipped.append(rel)
            continue
        current = path.read_text(encoding="utf-8") if path.exists() else None
        old_content = old_writes.get(rel)
        if current is None or current == old_content or current == new_content:
            planned[rel] = new_content
        else:
            conflicts.append(rel)
            if args.conflict == "inline":
                planned[rel] = (
                    "<<<<<<< local\n"
                    + current
                    + ("\n" if not current.endswith("\n") else "")
                    + "=======\n"
                    + new_content
                    + ("\n" if not new_content.endswith("\n") else "")
                    + ">>>>>>> template\n"
                )
            else:
                reject_writes[rel + ".rej"] = new_content
    if args.pretend:
        return {
            "ok": True,
            "command": "update",
            "operation": "update",
            "pretend": True,
            "answers_file": answers_file,
            "commit": new_template.commit,
            "written": sorted(list(planned) + list(reject_writes)),
            "skipped": sorted(skipped),
            "excluded": excluded,
            "conflicts": sorted(conflicts),
        }
    if args.trust and before_actions:
        apply_actions(args.dest, before_actions)
    written = apply_writes(args.dest, planned)
    written += apply_writes(args.dest, reject_writes)
    if args.trust and after_actions:
        apply_actions(args.dest, after_actions)
    payload = answers_payload(new_template, new_template.commit, answers, skipped_questions, secrets)
    write_answers_file(args.dest, answers_file, payload)
    if new_settings["_tasks"] and not args.skip_tasks:
        apply_actions(args.dest, new_settings["_tasks"])
    result = {
        "ok": True,
        "command": "update",
        "operation": "update",
        "answers_file": answers_file,
        "commit": new_template.commit,
        "written": sorted(written),
        "skipped": sorted(skipped),
        "excluded": excluded,
    }
    if conflicts:
        result["conflicts"] = sorted(conflicts)
    return result


def build_parser():
    parser = argparse.ArgumentParser(prog="minicopier.py")
    sub = parser.add_subparsers(dest="command", required=True)

    copy = sub.add_parser("copy")
    copy.add_argument("template")
    copy.add_argument("dest")
    copy.add_argument("--answers-file")
    copy.add_argument("--data", action="append", default=[])
    copy.add_argument("--data-file")
    copy.add_argument("--defaults", action="store_true")
    copy.add_argument("--overwrite", action="store_true")
    copy.add_argument("--exclude", action="append", default=[])
    copy.add_argument("--skip", action="append", default=[])
    copy.add_argument("--vcs-ref")
    copy.add_argument("--pretend", action="store_true")
    copy.add_argument("--trust", action="store_true")
    copy.add_argument("--skip-tasks", action="store_true")
    copy.set_defaults(func=command_copy)

    recopy = sub.add_parser("recopy")
    recopy.add_argument("dest")
    recopy.add_argument("--answers-file")
    recopy.add_argument("--data", action="append", default=[])
    recopy.add_argument("--overwrite", action="store_true")
    recopy.add_argument("--skip-answered", action="store_true")
    recopy.add_argument("--exclude", action="append", default=[])
    recopy.add_argument("--skip", action="append", default=[])
    recopy.add_argument("--pretend", action="store_true")
    recopy.set_defaults(func=command_recopy)

    update = sub.add_parser("update")
    update.add_argument("dest")
    update.add_argument("--answers-file")
    update.add_argument("--vcs-ref")
    update.add_argument("--data", action="append", default=[])
    update.add_argument("--overwrite", action="store_true")
    update.add_argument("--skip-answered", action="store_true")
    update.add_argument("--exclude", action="append", default=[])
    update.add_argument("--skip", action="append", default=[])
    update.add_argument("--conflict", choices=["inline", "rej"], default="inline")
    update.add_argument("--pretend", action="store_true")
    update.add_argument("--trust", action="store_true")
    update.add_argument("--skip-tasks", action="store_true")
    update.set_defaults(func=command_update)

    check = sub.add_parser("check-update")
    check.add_argument("dest")
    check.add_argument("--answers-file")
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=command_check_update)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except MiniCopierError as exc:
        return fail(str(exc))
    except Exception as exc:
        return fail(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

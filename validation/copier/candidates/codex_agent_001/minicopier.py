#!/usr/bin/env python3
"""A small deterministic Copier-like CLI built from the public PRD."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - tiny fallback for dependency-light runs
    yaml = None


DEFAULT_ANSWERS = ".copier-answers.yml"
CONFIG_NAMES = ("copier.yml", "copier.yaml")
FALSE_STRINGS = {"", "false", "False", "0", "no"}
VAR_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


class MiniError(Exception):
    pass


@dataclass
class TemplateView:
    source: Path
    root: Path
    is_git: bool
    commit: str | None = None
    temporary: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self.temporary is not None:
            self.temporary.cleanup()


@dataclass
class RenderPlan:
    writes: dict[str, str] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    rejects: dict[str, str] = field(default_factory=dict)


def load_yaml_text(text: str, label: str) -> Any:
    if yaml is not None:
        try:
            value = yaml.safe_load(text)
        except Exception as exc:
            raise MiniError(f"malformed YAML in {label}: {exc}") from exc
        return {} if value is None else value
    return parse_simple_yaml(text, label)


def parse_simple_yaml(text: str, label: str) -> Any:
    """Very small fallback parser for simple mappings/lists used by the PRD."""
    result: dict[str, Any] = {}
    lines = [line.rstrip("\n") for line in text.splitlines()]
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if raw.startswith(" "):
            raise MiniError(f"malformed YAML in {label}")
        if ":" not in raw:
            raise MiniError(f"malformed YAML in {label}")
        key, rest = raw.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest:
            result[key] = parse_scalar(rest)
            i += 1
            continue
        i += 1
        children: list[str] = []
        while i < len(lines) and (not lines[i].strip() or lines[i].startswith(" ")):
            if lines[i].strip():
                children.append(lines[i])
            i += 1
        result[key] = parse_child_block(children, label)
    return result


def parse_child_block(lines: list[str], label: str) -> Any:
    if not lines:
        return {}
    if all(line.lstrip().startswith("- ") for line in lines):
        return [parse_scalar(line.lstrip()[2:].strip()) for line in lines]
    mapping: dict[str, Any] = {}
    for line in lines:
        stripped = line.strip()
        if ":" not in stripped:
            raise MiniError(f"malformed YAML in {label}")
        key, rest = stripped.split(":", 1)
        mapping[key.strip()] = parse_scalar(rest.strip()) if rest.strip() else {}
    return mapping


def parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def dump_yaml(data: dict[str, Any]) -> str:
    if yaml is not None:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif value is None:
            rendered = "null"
        elif isinstance(value, (int, float)):
            rendered = str(value)
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines) + "\n"


def read_yaml_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = load_yaml_text(path.read_text(encoding="utf-8"), label)
    except UnicodeDecodeError as exc:
        raise MiniError(f"{label} is not valid UTF-8 text") from exc
    if not isinstance(value, dict):
        raise MiniError(f"{label} must contain a mapping")
    return value


def run_git(repo: Path, args: list[str], *, stdout: Any = subprocess.PIPE) -> subprocess.CompletedProcess[Any]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            stdout=stdout,
            stderr=subprocess.PIPE,
            text=True if stdout == subprocess.PIPE else False,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MiniError("local git executable is required for Git templates") from exc
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace") if isinstance(proc.stderr, bytes) else proc.stderr
        raise MiniError(err.strip() or "git command failed")
    return proc


def is_remote_source(source: str) -> bool:
    return bool(re.search(r"^[A-Za-z][A-Za-z0-9+.-]*://", source) or source.startswith("git@"))


def is_git_repo(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def newest_semver_tag(repo: Path) -> str | None:
    proc = run_git(repo, ["tag", "--list"])
    best: tuple[int, int, int, str] | None = None
    for tag in proc.stdout.splitlines():
        match = SEMVER_RE.match(tag.strip())
        if not match:
            continue
        version = tuple(int(part) for part in match.groups())
        candidate = (version[0], version[1], version[2], tag.strip())
        if best is None or candidate[:3] > best[:3] or (candidate[:3] == best[:3] and candidate[3] > best[3]):
            best = candidate
    return best[3] if best else None


def validate_git_ref(repo: Path, ref: str) -> None:
    run_git(repo, ["rev-parse", "--verify", f"{ref}^{{commit}}"])


def materialize_template(source_text: str, vcs_ref: str | None = None, default_to_stored: str | None = None) -> TemplateView:
    if is_remote_source(source_text):
        raise MiniError("remote template sources are unsupported")
    source = Path(source_text).expanduser().resolve()
    if not source.exists() or not source.is_dir():
        raise MiniError(f"missing template: {source_text}")
    if not is_git_repo(source):
        return TemplateView(source=source, root=source, is_git=False)

    if vcs_ref:
        selected = vcs_ref
        validate_git_ref(source, selected)
    elif default_to_stored:
        selected = default_to_stored
        validate_git_ref(source, selected)
    else:
        selected = newest_semver_tag(source) or "HEAD"
        validate_git_ref(source, selected)

    tmp = tempfile.TemporaryDirectory(prefix="minicopier-git-")
    archive = subprocess.Popen(
        ["git", "-C", str(source), "archive", "--format=tar", selected],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert archive.stdout is not None
    try:
        with tarfile.open(fileobj=archive.stdout, mode="r|") as tar:
            tar.extractall(tmp.name)
    except Exception as exc:
        archive.kill()
        raise MiniError(f"could not read Git ref {selected}") from exc
    _, stderr = archive.communicate()
    if archive.returncode != 0:
        tmp.cleanup()
        raise MiniError(stderr.decode("utf-8", "replace").strip() or f"could not read Git ref {selected}")
    return TemplateView(source=source, root=Path(tmp.name), is_git=True, commit=selected, temporary=tmp)


def load_config(root: Path) -> tuple[dict[str, Any], str | None]:
    for name in CONFIG_NAMES:
        path = root / name
        if path.exists():
            return read_yaml_file(path, name), name
    return {}, None


def expect_list(value: Any, name: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise MiniError(f"{name} must be a list")
    return value


def expect_string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise MiniError(f"{name} must be a string")
    return value


def validate_config(config: dict[str, Any]) -> None:
    for key in ("_exclude", "_skip_if_exists", "_tasks", "_secret_questions", "_migrations"):
        if key in config:
            expect_list(config[key], key)
    for key in ("_answers_file", "_templates_suffix", "_subdirectory"):
        if key in config and not isinstance(config[key], str):
            raise MiniError(f"{key} must be a string")


def render_value(text: Any, answers: dict[str, Any]) -> str:
    source = "" if text is None else str(text)
    return VAR_RE.sub(lambda match: str(answers.get(match.group(1), "")), source)


def falsey_rendered(text: str) -> bool:
    return text.strip() in FALSE_STRINGS


def parse_data_pairs(pairs: list[str] | None) -> dict[str, str]:
    values: dict[str, str] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise MiniError(f"invalid --data value {pair!r}; expected KEY=VALUE")
        key, value = pair.split("=", 1)
        if not key:
            raise MiniError("invalid --data key")
        values[key] = value
    return values


def load_data_file(path_text: str | None) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.exists():
        raise MiniError(f"missing data file: {path_text}")
    return read_yaml_file(path, "data file")


def question_defaults(config: dict[str, Any], base: dict[str, Any] | None = None) -> tuple[dict[str, Any], set[str]]:
    answers: dict[str, Any] = dict(base or {})
    skipped: set[str] = set()
    for key, spec in config.items():
        if key.startswith("_"):
            continue
        if isinstance(spec, dict):
            if "when" in spec and falsey_rendered(render_value(spec["when"], answers)):
                skipped.add(key)
                answers.pop(key, None)
                continue
            if "default" in spec and key not in answers:
                answers[key] = spec["default"]
        else:
            if key not in answers:
                answers[key] = spec
    return answers, skipped


def resolve_answers(
    config: dict[str, Any],
    existing: dict[str, Any] | None,
    data_file: dict[str, Any],
    cli_data: dict[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    defaults, _ = question_defaults(config)
    merged = defaults
    if existing:
        merged.update({k: v for k, v in existing.items() if not k.startswith("_")})
    merged.update(data_file)
    merged.update(cli_data)
    return question_defaults(config, merged)


def secret_keys(config: dict[str, Any]) -> set[str]:
    keys = {str(item) for item in expect_list(config.get("_secret_questions"), "_secret_questions")}
    for key, spec in config.items():
        if key.startswith("_"):
            continue
        if isinstance(spec, dict) and spec.get("secret") is True:
            keys.add(key)
    return keys


def answers_for_file(
    source: Path,
    commit: str | None,
    answers: dict[str, Any],
    config: dict[str, Any],
    skipped_questions: set[str],
) -> dict[str, Any]:
    hidden = secret_keys(config) | skipped_questions
    data: dict[str, Any] = {"_src_path": str(source)}
    if commit is not None:
        data["_commit"] = commit
    for key, value in answers.items():
        if key.startswith("_") or key in hidden:
            continue
        data[key] = value
    return data


def normalize_rel(path: str) -> str:
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part == ".." for part in pure.parts):
        raise MiniError(f"path escapes destination: {path}")
    normalized = pure.as_posix().strip("/")
    if not normalized or normalized == ".":
        raise MiniError("empty destination path")
    return normalized


def flatten_patterns(values: list[list[str]] | None) -> list[str]:
    return [item for group in values or [] for item in group]


def match_pattern(path: str, pattern: str) -> bool:
    pattern = pattern.replace(os.sep, "/")
    if pattern.endswith("/"):
        prefix = pattern.rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatchcase(path, pattern)


def any_match(path: str, patterns: list[str]) -> bool:
    return any(match_pattern(path, pattern) for pattern in patterns)


def render_rel_path(relative: Path, suffix: str, answers: dict[str, Any]) -> tuple[str | None, bool]:
    rendered_parts: list[str] = []
    for part in relative.parts:
        rendered = render_value(part, answers)
        if rendered == "":
            return None, False
        rendered_parts.append(rendered)
    rel = PurePosixPath(*rendered_parts).as_posix()
    was_template = rel.endswith(suffix)
    if suffix and was_template:
        rel = rel[: -len(suffix)]
    return normalize_rel(rel), was_template


def render_template_tree(
    view: TemplateView,
    config: dict[str, Any],
    answers: dict[str, Any],
    dest: Path,
    cli_exclude: list[str],
    cli_skip: list[str],
) -> RenderPlan:
    suffix = str(config.get("_templates_suffix", ".jinja"))
    exclude = [str(item) for item in expect_list(config.get("_exclude"), "_exclude")] + cli_exclude
    skip = [str(item) for item in expect_list(config.get("_skip_if_exists"), "_skip_if_exists")] + cli_skip
    subdir = config.get("_subdirectory")
    base = view.root / subdir if isinstance(subdir, str) else view.root
    if not base.exists() or not base.is_dir():
        raise MiniError("template subdirectory is missing")

    plan = RenderPlan()
    for item in sorted(base.rglob("*")):
        if not item.is_file() or item.is_symlink():
            continue
        source_rel_from_root = item.relative_to(view.root).as_posix()
        if source_rel_from_root in CONFIG_NAMES:
            continue
        relative = item.relative_to(base)
        rendered_rel, is_template = render_rel_path(relative, suffix, answers)
        if rendered_rel is None:
            continue
        if any_match(rendered_rel, exclude):
            plan.excluded.append(rendered_rel)
            continue
        if any_match(rendered_rel, skip) and (dest / rendered_rel).exists():
            plan.skipped.append(rendered_rel)
            continue
        try:
            raw = item.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise MiniError(f"binary or non-text file unsupported: {relative.as_posix()}") from exc
        plan.writes[rendered_rel] = render_value(raw, answers) if is_template else raw
    return plan


def ensure_inside(dest: Path, rel: str) -> Path:
    normalized = normalize_rel(rel)
    target = (dest / normalized).resolve()
    dest_resolved = dest.resolve()
    if target != dest_resolved and dest_resolved not in target.parents:
        raise MiniError(f"path escapes destination: {rel}")
    return target


def check_copy_overwrites(plan: RenderPlan, dest: Path, overwrite: bool, answers_rel: str) -> None:
    for rel in plan.writes:
        if rel == answers_rel:
            continue
        if (dest / rel).exists() and not overwrite:
            raise MiniError(f"destination file exists; use --overwrite: {rel}")


def parse_action(action: str) -> tuple[str, str, str]:
    parts = action.split(" ", 2)
    if len(parts) != 3 or parts[0] not in {"write", "append"}:
        raise MiniError(f"unsupported safe action: {action}")
    return parts[0], normalize_rel(parts[1]), parts[2]


def collect_actions(items: Any, label: str) -> list[tuple[str, str, str]]:
    actions: list[tuple[str, str, str]] = []
    for item in expect_list(items, label):
        if not isinstance(item, str):
            raise MiniError(f"{label} entries must be strings")
        actions.append(parse_action(item))
    return actions


def collect_migration_actions(config: dict[str, Any], phase: str) -> list[tuple[str, str, str]]:
    actions: list[tuple[str, str, str]] = []
    for migration in expect_list(config.get("_migrations"), "_migrations"):
        if not isinstance(migration, dict):
            raise MiniError("_migrations entries must be mappings")
        for action in expect_list(migration.get(phase), f"_migrations.{phase}"):
            if not isinstance(action, str):
                raise MiniError("migration actions must be strings")
            actions.append(parse_action(action))
    return actions


def require_trust_for_actions(config: dict[str, Any], trust: bool, skip_tasks: bool, command: str) -> None:
    has_tasks = bool(expect_list(config.get("_tasks"), "_tasks"))
    has_migrations = bool(expect_list(config.get("_migrations"), "_migrations"))
    if has_tasks and not trust and not skip_tasks:
        raise MiniError("template tasks require --trust or --skip-tasks")
    if command == "update" and has_migrations and not trust:
        raise MiniError("template migrations require --trust")


def backup_paths(paths: list[Path]) -> dict[Path, bytes | None]:
    backups: dict[Path, bytes | None] = {}
    for path in paths:
        if path in backups:
            continue
        backups[path] = path.read_bytes() if path.exists() else None
    return backups


def restore_backups(backups: dict[Path, bytes | None]) -> None:
    for path, content in backups.items():
        if content is None:
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def prune_empty_dirs(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass


def apply_actions(dest: Path, actions: list[tuple[str, str, str]]) -> list[Path]:
    touched: list[Path] = []
    for verb, rel, text in actions:
        target = ensure_inside(dest, rel)
        touched.append(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if verb == "write":
            target.write_text(text, encoding="utf-8")
        else:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(text + "\n")
    return touched


def apply_plan(
    dest: Path,
    plan: RenderPlan,
    answers_rel: str | None,
    answers_text: str | None,
    before_actions: list[tuple[str, str, str]] | None = None,
    after_actions: list[tuple[str, str, str]] | None = None,
    remove_new_dest_on_error: bool = False,
) -> None:
    before_actions = before_actions or []
    after_actions = after_actions or []
    paths: list[Path] = []
    for rel in plan.writes:
        paths.append(ensure_inside(dest, rel))
    for rel in plan.rejects:
        paths.append(ensure_inside(dest, rel))
    if answers_rel and answers_text is not None:
        paths.append(ensure_inside(dest, answers_rel))
    for _, rel, _ in before_actions + after_actions:
        paths.append(ensure_inside(dest, rel))
    backups = backup_paths(paths)
    try:
        dest.mkdir(parents=True, exist_ok=True)
        apply_actions(dest, before_actions)
        for rel, content in plan.writes.items():
            target = ensure_inside(dest, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for rel, content in plan.rejects.items():
            target = ensure_inside(dest, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        if answers_rel and answers_text is not None:
            target = ensure_inside(dest, answers_rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(answers_text, encoding="utf-8")
        apply_actions(dest, after_actions)
    except Exception:
        restore_backups(backups)
        if remove_new_dest_on_error and dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        else:
            prune_empty_dirs(dest)
        raise


def relative_answers_path(args_answers: str | None, config: dict[str, Any] | None = None) -> str:
    rel = args_answers or (config or {}).get("_answers_file") or DEFAULT_ANSWERS
    return normalize_rel(str(rel))


def load_project_answers(dest: Path, answers_arg: str | None) -> tuple[dict[str, Any], str]:
    rel = normalize_rel(answers_arg or DEFAULT_ANSWERS)
    path = dest / rel
    if not path.exists():
        if answers_arg is None:
            raise MiniError("missing destination answers file; use --answers-file for non-default paths")
        raise MiniError(f"missing destination answers file: {rel}")
    return read_yaml_file(path, "answers file"), rel


def command_copy(args: argparse.Namespace) -> dict[str, Any]:
    view = materialize_template(args.template, args.vcs_ref)
    try:
        config, _ = load_config(view.root)
        validate_config(config)
        require_trust_for_actions(config, args.trust, args.skip_tasks, "copy")
        cli_data = parse_data_pairs(args.data)
        data_file = load_data_file(args.data_file)
        answers, skipped_questions = resolve_answers(config, None, data_file, cli_data)
        dest = Path(args.dest).resolve()
        answers_rel = relative_answers_path(args.answers_file, config)
        plan = render_template_tree(view, config, answers, dest, flatten_patterns(args.exclude), flatten_patterns(args.skip))
        check_copy_overwrites(plan, dest, args.overwrite, answers_rel)
        answers_data = answers_for_file(view.source, view.commit, answers, config, skipped_questions)
        answers_text = dump_yaml(answers_data)
        tasks = [] if args.skip_tasks else collect_actions(config.get("_tasks"), "_tasks")
        result = {
            "ok": True,
            "command": "copy",
            "operation": "copy",
            "answers_file": answers_rel,
            "written": sorted(plan.writes),
            "skipped": sorted(plan.skipped),
            "excluded": sorted(plan.excluded),
        }
        if view.commit is not None:
            result["commit"] = view.commit
        if args.pretend:
            result["pretend"] = True
            return result
        existed = dest.exists()
        apply_plan(dest, plan, answers_rel, answers_text, after_actions=tasks, remove_new_dest_on_error=not existed)
        return result
    finally:
        view.close()


def command_recopy(args: argparse.Namespace) -> dict[str, Any]:
    dest = Path(args.dest).resolve()
    existing_answers, answers_rel = load_project_answers(dest, args.answers_file)
    source = existing_answers.get("_src_path")
    if not source:
        raise MiniError("answers file lacks _src_path")
    stored_commit = existing_answers.get("_commit")
    view = materialize_template(str(source), default_to_stored=str(stored_commit) if stored_commit else None)
    try:
        config, _ = load_config(view.root)
        validate_config(config)
        require_trust_for_actions(config, False, False, "recopy")
        # Recopy has no --trust option in the public CLI; tasks must be skipped by absence.
        if expect_list(config.get("_tasks"), "_tasks"):
            raise MiniError("template tasks require --trust or --skip-tasks")
        cli_data = parse_data_pairs(args.data)
        base_existing = existing_answers if args.skip_answered else existing_answers
        answers, skipped_questions = resolve_answers(config, base_existing, {}, cli_data)
        plan = render_template_tree(view, config, answers, dest, flatten_patterns(args.exclude), flatten_patterns(args.skip))
        answers_data = answers_for_file(view.source, view.commit, answers, config, skipped_questions)
        answers_text = dump_yaml(answers_data)
        result = {
            "ok": True,
            "command": "recopy",
            "operation": "recopy",
            "answers_file": answers_rel,
            "commit": view.commit,
            "written": sorted(plan.writes),
            "skipped": sorted(plan.skipped),
            "excluded": sorted(plan.excluded),
        }
        if args.pretend:
            result["pretend"] = True
            return result
        apply_plan(dest, plan, answers_rel, answers_text)
        return result
    finally:
        view.close()


def command_check_update(args: argparse.Namespace) -> dict[str, Any]:
    dest = Path(args.dest).resolve()
    answers, _ = load_project_answers(dest, args.answers_file)
    source = answers.get("_src_path")
    if not source:
        raise MiniError("answers file lacks _src_path")
    source_path = Path(str(source)).expanduser().resolve()
    if not is_git_repo(source_path):
        latest = answers.get("_commit")
    else:
        latest = newest_semver_tag(source_path) or "HEAD"
    current = answers.get("_commit")
    return {
        "ok": True,
        "command": "check-update",
        "current": current,
        "latest": latest,
        "update_available": bool(latest and current != latest),
    }


def command_update(args: argparse.Namespace) -> dict[str, Any]:
    dest = Path(args.dest).resolve()
    existing_answers, answers_rel = load_project_answers(dest, args.answers_file)
    source = existing_answers.get("_src_path")
    old_commit = existing_answers.get("_commit")
    if not source:
        raise MiniError("answers file lacks _src_path")
    old_view = materialize_template(str(source), default_to_stored=str(old_commit) if old_commit else None)
    new_view = materialize_template(str(source), args.vcs_ref)
    try:
        old_config, _ = load_config(old_view.root)
        new_config, _ = load_config(new_view.root)
        validate_config(old_config)
        validate_config(new_config)
        require_trust_for_actions(new_config, args.trust, args.skip_tasks, "update")
        cli_data = parse_data_pairs(args.data)
        old_answers, _ = resolve_answers(old_config, existing_answers, {}, {})
        new_answers, skipped_questions = resolve_answers(new_config, existing_answers, {}, cli_data)
        old_plan = render_template_tree(old_view, old_config, old_answers, dest, flatten_patterns(args.exclude), flatten_patterns(args.skip))
        new_plan = render_template_tree(new_view, new_config, new_answers, dest, flatten_patterns(args.exclude), flatten_patterns(args.skip))
        final_plan = RenderPlan(skipped=new_plan.skipped, excluded=new_plan.excluded)
        for rel, new_content in new_plan.writes.items():
            target = dest / rel
            old_content = old_plan.writes.get(rel)
            current_exists = target.exists()
            current = target.read_text(encoding="utf-8") if current_exists else None
            if current == new_content:
                continue
            if not current_exists or current == old_content:
                final_plan.writes[rel] = new_content
                continue
            final_plan.conflicts.append(rel)
            if args.conflict == "inline":
                final_plan.writes[rel] = (
                    "<<<<<<< local\n"
                    + (current or "")
                    + ("\n" if current and not current.endswith("\n") else "")
                    + "=======\n"
                    + new_content
                    + ("\n" if new_content and not new_content.endswith("\n") else "")
                    + ">>>>>>> template\n"
                )
            else:
                final_plan.rejects[rel + ".rej"] = new_content
        answers_data = answers_for_file(new_view.source, new_view.commit, new_answers, new_config, skipped_questions)
        answers_text = dump_yaml(answers_data)
        before = collect_migration_actions(new_config, "before") if args.trust else []
        after = collect_migration_actions(new_config, "after") if args.trust else []
        if not args.skip_tasks:
            after += collect_actions(new_config.get("_tasks"), "_tasks")
        result = {
            "ok": True,
            "command": "update",
            "operation": "update",
            "answers_file": answers_rel,
            "commit": new_view.commit,
            "written": sorted(final_plan.writes),
            "skipped": sorted(final_plan.skipped),
            "excluded": sorted(final_plan.excluded),
        }
        if final_plan.conflicts:
            result["conflicts"] = sorted(final_plan.conflicts)
        if args.pretend:
            result["pretend"] = True
            return result
        apply_plan(dest, final_plan, answers_rel, answers_text, before_actions=before, after_actions=after)
        return result
    finally:
        old_view.close()
        new_view.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minicopier.py")
    sub = parser.add_subparsers(dest="command", required=True)

    copy = sub.add_parser("copy")
    copy.add_argument("template")
    copy.add_argument("dest")
    copy.add_argument("--answers-file")
    copy.add_argument("--data", action="append")
    copy.add_argument("--data-file")
    copy.add_argument("--defaults", action="store_true")
    copy.add_argument("--overwrite", action="store_true")
    copy.add_argument("--exclude", action="append", nargs="+")
    copy.add_argument("--skip", action="append", nargs="+")
    copy.add_argument("--vcs-ref")
    copy.add_argument("--pretend", action="store_true")
    copy.add_argument("--trust", action="store_true")
    copy.add_argument("--skip-tasks", action="store_true")
    copy.set_defaults(func=command_copy)

    recopy = sub.add_parser("recopy")
    recopy.add_argument("dest")
    recopy.add_argument("--answers-file")
    recopy.add_argument("--data", action="append")
    recopy.add_argument("--overwrite", action="store_true")
    recopy.add_argument("--skip-answered", action="store_true")
    recopy.add_argument("--exclude", action="append", nargs="+")
    recopy.add_argument("--skip", action="append", nargs="+")
    recopy.add_argument("--pretend", action="store_true")
    recopy.set_defaults(func=command_recopy)

    update = sub.add_parser("update")
    update.add_argument("dest")
    update.add_argument("--answers-file")
    update.add_argument("--vcs-ref")
    update.add_argument("--data", action="append")
    update.add_argument("--overwrite", action="store_true")
    update.add_argument("--skip-answered", action="store_true")
    update.add_argument("--exclude", action="append", nargs="+")
    update.add_argument("--skip", action="append", nargs="+")
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        result = args.func(args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except MiniError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

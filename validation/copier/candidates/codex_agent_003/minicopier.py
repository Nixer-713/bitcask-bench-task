#!/usr/bin/env python3
"""A small deterministic Copier-like CLI.

Implemented from the public PRD for task/copier-realrepo-001.
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback for minimal environments
    yaml = None


CONFIG_NAMES = {"copier.yml", "copier.yaml"}
FALSEY_WHEN = {"", "false", "False", "0", "no"}
VAR_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


class MiniError(Exception):
    pass


@dataclass
class Template:
    source: str
    root: Path
    is_git: bool
    commit: str | None
    tempdir: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self.tempdir is not None:
            self.tempdir.cleanup()


@dataclass
class Config:
    raw: dict[str, Any]
    answers_file: str = ".copier-answers.yml"
    suffix: str = ".jinja"
    exclude: list[str] | None = None
    skip: list[str] | None = None
    subdirectory: str | None = None
    tasks: list[Any] | None = None
    migrations: list[Any] | None = None
    secret_questions: list[str] | None = None


@dataclass
class RenderPlan:
    files: dict[str, bytes]
    skipped: list[str]
    excluded: list[str]


def fail(message: str) -> None:
    raise MiniError(message)


def render_string(text: str, answers: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        value = answers.get(match.group(1), "")
        return "" if value is None else str(value)

    return VAR_RE.sub(repl, text)


def load_yaml_file(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"missing file: {path}")
    except UnicodeDecodeError:
        fail(f"malformed YAML file: {path}")

    if not text.strip():
        return {}
    if yaml is not None:
        try:
            return yaml.safe_load(text)
        except Exception as exc:
            fail(f"malformed YAML file {path}: {exc}")
    return load_simple_yaml(text, path)


def load_simple_yaml(text: str, path: Path) -> Any:
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - ") and current_key:
            result.setdefault(current_key, []).append(parse_scalar(raw_line[4:].strip()))
            continue
        if raw_line.startswith("  ") and current_key:
            if not isinstance(result.get(current_key), dict):
                result[current_key] = {}
            key, sep, value = raw_line.strip().partition(":")
            if not sep:
                fail(f"malformed YAML file {path}")
            result[current_key][key] = parse_scalar(value.strip())
            continue
        key, sep, value = raw_line.partition(":")
        if not sep:
            fail(f"malformed YAML file {path}")
        current_key = key.strip()
        if value.strip() == "":
            result[current_key] = []
        else:
            result[current_key] = parse_scalar(value.strip())
    return result


def parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", "~"}:
        return None
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def dump_yaml(data: dict[str, Any]) -> str:
    if yaml is not None:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def is_remote_source(source: str) -> bool:
    return "://" in source or source.startswith("git@") or source.startswith("ssh:")


def run_git(repo: Path, args: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError:
        fail("git executable is required for local Git templates")
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip()
        fail(detail or f"git command failed: {' '.join(args)}")


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def semver_key(ref: str) -> tuple[int, int, int] | None:
    match = SEMVER_RE.match(ref)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def newest_semver_tag(repo: Path) -> str | None:
    result = run_git(repo, ["tag", "--list"])
    tags = [line.strip() for line in result.stdout.decode().splitlines() if line.strip()]
    semver_tags = [(semver_key(tag), tag) for tag in tags if semver_key(tag) is not None]
    if not semver_tags:
        return None
    semver_tags.sort(key=lambda item: (item[0], item[1]))  # type: ignore[arg-type]
    return semver_tags[-1][1]


def select_git_ref(repo: Path, explicit: str | None) -> str:
    if explicit:
        run_git(repo, ["rev-parse", "--verify", f"{explicit}^{{tree}}"])
        return explicit
    tag = newest_semver_tag(repo)
    if tag:
        return tag
    run_git(repo, ["rev-parse", "--verify", "HEAD^{tree}"])
    return "HEAD"


def open_template(source: str, vcs_ref: str | None = None, stored_ref: str | None = None) -> Template:
    if is_remote_source(source):
        fail("remote template sources are unsupported")
    src_path = Path(source).expanduser()
    if not src_path.exists():
        fail(f"missing template: {source}")
    src_path = src_path.resolve()

    if is_git_repo(src_path):
        commit = stored_ref if stored_ref is not None else select_git_ref(src_path, vcs_ref)
        if stored_ref is not None:
            run_git(src_path, ["rev-parse", "--verify", f"{stored_ref}^{{tree}}"])
        temp = tempfile.TemporaryDirectory(prefix="minicopier-git-")
        archive = run_git(src_path, ["archive", "--format=tar", commit])
        with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
            try:
                tar.extractall(temp.name, filter="data")
            except TypeError:  # Older Python versions do not support filters.
                tar.extractall(temp.name)
        return Template(str(src_path), Path(temp.name), True, commit, temp)
    if vcs_ref:
        fail("--vcs-ref requires a local Git template")
    return Template(str(src_path), src_path, False, None, None)


def load_config(root: Path) -> Config:
    config_path = root / "copier.yml"
    if not config_path.exists():
        config_path = root / "copier.yaml"
    raw: dict[str, Any] = {}
    if config_path.exists():
        loaded = load_yaml_file(config_path)
        if loaded is None:
            raw = {}
        elif isinstance(loaded, dict):
            raw = loaded
        else:
            fail("template config must be a mapping")

    cfg = Config(raw=raw, exclude=[], skip=[], tasks=[], migrations=[], secret_questions=[])
    if "_answers_file" in raw:
        cfg.answers_file = require_type(raw["_answers_file"], str, "_answers_file")
    if "_templates_suffix" in raw:
        cfg.suffix = require_type(raw["_templates_suffix"], str, "_templates_suffix")
    if "_exclude" in raw:
        cfg.exclude = require_list(raw["_exclude"], "_exclude")
    if "_skip_if_exists" in raw:
        cfg.skip = require_list(raw["_skip_if_exists"], "_skip_if_exists")
    if "_subdirectory" in raw:
        cfg.subdirectory = require_type(raw["_subdirectory"], str, "_subdirectory")
    if "_tasks" in raw:
        cfg.tasks = require_list(raw["_tasks"], "_tasks")
    if "_migrations" in raw:
        cfg.migrations = require_list(raw["_migrations"], "_migrations")
    if "_secret_questions" in raw:
        cfg.secret_questions = require_list(raw["_secret_questions"], "_secret_questions")
    return cfg


def require_type(value: Any, typ: type, name: str) -> Any:
    if not isinstance(value, typ):
        fail(f"{name} has invalid type")
    return value


def require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{name} has invalid type")
    return value


def parse_data(items: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            fail(f"invalid --data value: {item}")
        key, value = item.split("=", 1)
        if not key:
            fail(f"invalid --data value: {item}")
        result[key] = value
    return result


def load_data_file(path_text: str | None) -> dict[str, Any]:
    if not path_text:
        return {}
    loaded = load_yaml_file(Path(path_text))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        fail("--data-file must contain a mapping")
    return loaded


def question_defaults(cfg: Config, base: dict[str, Any] | None = None) -> tuple[dict[str, Any], set[str], set[str]]:
    answers = dict(base or {})
    skipped: set[str] = set()
    secrets: set[str] = set(str(name) for name in (cfg.secret_questions or []))

    for key, spec in cfg.raw.items():
        if key.startswith("_"):
            continue
        if isinstance(spec, dict):
            if spec.get("secret") is True:
                secrets.add(key)
            if "default" in spec:
                answers.setdefault(key, spec["default"])
            else:
                answers.setdefault(key, "")
        else:
            answers.setdefault(key, spec)

    # Re-check conditions after defaults and caller-supplied answers are present.
    for key, spec in cfg.raw.items():
        if key.startswith("_") or not isinstance(spec, dict) or "when" not in spec:
            continue
        rendered = render_string(str(spec["when"]), answers).strip()
        if rendered in FALSEY_WHEN:
            skipped.add(key)
            answers.pop(key, None)
    return answers, skipped, secrets


def resolve_answers(
    cfg: Config,
    *,
    existing: dict[str, Any] | None = None,
    data_file: dict[str, Any] | None = None,
    cli_data: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], set[str], set[str]]:
    answers, skipped, secrets = question_defaults(cfg)
    for source in (existing or {}, data_file or {}, cli_data or {}):
        for key, value in source.items():
            if key.startswith("_"):
                continue
            answers[key] = value
    answers, skipped, secrets = question_defaults(cfg, answers)
    for key in skipped:
        answers.pop(key, None)
    return answers, skipped, secrets


def answer_file_rel(args: argparse.Namespace, cfg: Config | None = None, *, for_copy: bool = False) -> str:
    if getattr(args, "answers_file", None):
        rel = args.answers_file
    elif for_copy and cfg is not None:
        rel = cfg.answers_file
    else:
        rel = ".copier-answers.yml"
    validate_relative_path(rel, "answers file")
    return rel


def validate_relative_path(rel: str, label: str) -> None:
    pure = PurePosixPath(rel.replace(os.sep, "/"))
    if pure.is_absolute() or any(part == ".." for part in pure.parts):
        fail(f"{label} path must stay inside destination")


def safe_dest_path(dest: Path, rel: str) -> Path:
    validate_relative_path(rel, rel)
    root = dest.resolve()
    path = (root / Path(*PurePosixPath(rel).parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        fail(f"path escapes destination: {rel}")
    return path


def match_pattern(pattern: str, rel: str) -> bool:
    pattern = pattern.replace("\\", "/")
    rel = rel.replace("\\", "/")
    if pattern.endswith("/"):
        prefix = pattern.rstrip("/")
        return rel == prefix or rel.startswith(prefix + "/")
    return fnmatch.fnmatchcase(rel, pattern)


def any_match(patterns: list[str], rel: str) -> bool:
    return any(match_pattern(str(pattern), rel) for pattern in patterns)


def render_rel_path(path: PurePosixPath, suffix: str, answers: dict[str, Any]) -> str | None:
    rendered_parts: list[str] = []
    for part in path.parts:
        rendered = render_string(part, answers)
        if rendered == "":
            return None
        rendered_parts.append(rendered)
    if rendered_parts and suffix and rendered_parts[-1].endswith(suffix):
        rendered_parts[-1] = rendered_parts[-1][: -len(suffix)]
        if rendered_parts[-1] == "":
            return None
    return str(PurePosixPath(*rendered_parts))


def render_template_files(
    root: Path,
    cfg: Config,
    answers: dict[str, Any],
    dest: Path,
    extra_exclude: list[str] | None = None,
    extra_skip: list[str] | None = None,
) -> RenderPlan:
    render_root = root
    if cfg.subdirectory:
        validate_relative_path(cfg.subdirectory, "_subdirectory")
        render_root = root / cfg.subdirectory
        if not render_root.is_dir():
            fail(f"missing template subdirectory: {cfg.subdirectory}")

    exclude_patterns = [str(p) for p in (cfg.exclude or [])] + [str(p) for p in (extra_exclude or [])]
    skip_patterns = [str(p) for p in (cfg.skip or [])] + [str(p) for p in (extra_skip or [])]
    files: dict[str, bytes] = {}
    skipped: list[str] = []
    excluded: list[str] = []

    for current, dirnames, filenames in os.walk(render_root):
        current_path = Path(current)
        rel_dir = current_path.relative_to(render_root)
        kept_dirs = []
        for dirname in dirnames:
            rel_tpl = PurePosixPath(*(rel_dir / dirname).parts)
            rendered_dir = render_rel_path(rel_tpl, cfg.suffix, answers)
            if rendered_dir is None:
                continue
            if any_match(exclude_patterns, rendered_dir + "/"):
                excluded.append(rendered_dir)
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            source_path = current_path / filename
            if source_path.is_symlink():
                continue
            rel_tpl_path = PurePosixPath(*(rel_dir / filename).parts)
            root_rel = source_path.relative_to(root).as_posix()
            if root_rel in CONFIG_NAMES:
                continue
            rendered_rel = render_rel_path(rel_tpl_path, cfg.suffix, answers)
            if rendered_rel is None:
                continue
            if any_match(exclude_patterns, rendered_rel):
                excluded.append(rendered_rel)
                continue
            target = dest / Path(*PurePosixPath(rendered_rel).parts)
            if target.exists() and any_match(skip_patterns, rendered_rel):
                skipped.append(rendered_rel)
                continue
            if filename.endswith(cfg.suffix):
                try:
                    text = source_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    fail(f"template file is not text: {rel_tpl_path}")
                files[rendered_rel] = render_string(text, answers).encode("utf-8")
            else:
                files[rendered_rel] = source_path.read_bytes()
    return RenderPlan(files, sorted(set(skipped)), sorted(set(excluded)))


def public_answers(
    template: Template,
    answers: dict[str, Any],
    secrets: set[str],
    skipped: set[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {"_src_path": template.source}
    if template.commit is not None:
        result["_commit"] = template.commit
    for key, value in answers.items():
        if key not in secrets and key not in skipped and not key.startswith("_"):
            result[key] = value
    return result


def load_answers(dest: Path, rel: str) -> dict[str, Any]:
    path = safe_dest_path(dest, rel)
    if not path.exists():
        fail(f"missing destination answers file: {rel}")
    loaded = load_yaml_file(path)
    if not isinstance(loaded, dict):
        fail("answers file must be a mapping")
    return loaded


def parse_action(action: Any) -> tuple[str, str, str]:
    if not isinstance(action, str):
        fail("safe actions must be strings")
    op, sep, rest = action.partition(" ")
    if not sep or op not in {"write", "append"}:
        fail(f"unsupported safe action: {action}")
    file_part, sep, text = rest.partition(" ")
    if not sep or not file_part:
        fail(f"unsupported safe action: {action}")
    validate_relative_path(file_part, "safe action")
    return op, file_part, text


def planned_action_writes(
    dest: Path, actions: list[Any], overlay: dict[str, bytes] | None = None
) -> list[tuple[str, bytes]]:
    staged = overlay if overlay is not None else {}
    writes: list[tuple[str, bytes]] = []
    for action in actions:
        op, rel, text = parse_action(action)
        path = safe_dest_path(dest, rel)
        if op == "write":
            data = text.encode("utf-8")
        else:
            old = staged.get(rel)
            if old is None:
                old = path.read_bytes() if path.exists() else b""
            data = old + (text + "\n").encode("utf-8")
        staged[rel] = data
        writes.append((rel, data))
    return writes


def migration_actions(cfg: Config) -> tuple[list[Any], list[Any]]:
    before: list[Any] = []
    after: list[Any] = []
    for migration in cfg.migrations or []:
        if not isinstance(migration, dict):
            fail("migrations must be mappings")
        before.extend(require_list(migration.get("before", []), "migration before"))
        after.extend(require_list(migration.get("after", []), "migration after"))
    return before, after


def apply_writes(dest: Path, writes: list[tuple[str, bytes]], *, remove_dest_on_fail: bool = False) -> None:
    backups: dict[Path, bytes | None] = {}
    touched: list[Path] = []
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for rel, data in writes:
            path = safe_dest_path(dest, rel)
            if path not in backups:
                backups[path] = path.read_bytes() if path.exists() else None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            touched.append(path)
    except Exception as exc:
        for path in reversed(touched):
            original = backups.get(path)
            if original is None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            elif original is not None:
                path.write_bytes(original)
        for path, original in backups.items():
            if path not in touched and original is None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
        if remove_dest_on_fail:
            shutil.rmtree(dest, ignore_errors=True)
        if isinstance(exc, MiniError):
            raise
        fail(str(exc))


def validate_no_overwrite(dest: Path, rels: list[str]) -> None:
    conflicts = [rel for rel in rels if safe_dest_path(dest, rel).exists()]
    if conflicts:
        fail(f"destination files already exist; use --overwrite: {', '.join(sorted(conflicts))}")


def success(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, sort_keys=True))
    return 0


def command_copy(args: argparse.Namespace) -> int:
    template = open_template(args.template, args.vcs_ref)
    try:
        cfg = load_config(template.root)
        if (cfg.tasks or []) and not (args.trust or args.skip_tasks):
            fail("template tasks require --trust or --skip-tasks")
        dest = Path(args.dest).resolve()
        existed = dest.exists()
        data_file = load_data_file(args.data_file)
        answers, skipped_questions, secrets = resolve_answers(
            cfg, data_file=data_file, cli_data=parse_data(args.data)
        )
        plan = render_template_files(template.root, cfg, answers, dest, args.exclude, args.skip)
        if not args.overwrite:
            validate_no_overwrite(dest, list(plan.files))
        answers_rel = answer_file_rel(args, cfg, for_copy=True)
        answers_bytes = dump_yaml(public_answers(template, answers, secrets, skipped_questions)).encode("utf-8")
        writes = list(plan.files.items()) + [(answers_rel, answers_bytes)]
        if not args.skip_tasks:
            overlay = dict(writes)
            writes.extend(planned_action_writes(dest, cfg.tasks or [], overlay))
        if args.pretend:
            return success(
                {
                    "ok": True,
                    "command": "copy",
                    "operation": "copy",
                    "answers_file": answers_rel,
                    "commit": template.commit,
                    "pretend": True,
                    "written": sorted(plan.files),
                    "skipped": plan.skipped,
                    "excluded": plan.excluded,
                }
            )
        apply_writes(dest, writes, remove_dest_on_fail=not existed)
        return success(
            {
                "ok": True,
                "command": "copy",
                "operation": "copy",
                "answers_file": answers_rel,
                "commit": template.commit,
                "written": sorted(plan.files),
                "skipped": plan.skipped,
                "excluded": plan.excluded,
            }
        )
    finally:
        template.close()


def command_recopy(args: argparse.Namespace) -> int:
    dest = Path(args.dest).resolve()
    answers_rel = answer_file_rel(args)
    stored = load_answers(dest, answers_rel)
    src = stored.get("_src_path")
    if not src:
        fail("answers file lacks _src_path")
    template = open_template(str(src), stored_ref=stored.get("_commit"))
    try:
        cfg = load_config(template.root)
        if cfg.tasks:
            fail("template tasks require --trust or --skip-tasks")
        answers, skipped_questions, secrets = resolve_answers(
            cfg, existing=stored, cli_data=parse_data(args.data)
        )
        plan = render_template_files(template.root, cfg, answers, dest, args.exclude, args.skip)
        answers_bytes = dump_yaml(public_answers(template, answers, secrets, skipped_questions)).encode("utf-8")
        writes = list(plan.files.items()) + [(answers_rel, answers_bytes)]
        if args.pretend:
            return success(
                {
                    "ok": True,
                    "command": "recopy",
                    "operation": "recopy",
                    "answers_file": answers_rel,
                    "commit": template.commit,
                    "pretend": True,
                    "written": sorted(plan.files),
                    "skipped": plan.skipped,
                    "excluded": plan.excluded,
                }
            )
        apply_writes(dest, writes)
        return success(
            {
                "ok": True,
                "command": "recopy",
                "operation": "recopy",
                "answers_file": answers_rel,
                "commit": template.commit,
                "written": sorted(plan.files),
                "skipped": plan.skipped,
                "excluded": plan.excluded,
            }
        )
    finally:
        template.close()


def command_check_update(args: argparse.Namespace) -> int:
    dest = Path(args.dest).resolve()
    answers_rel = answer_file_rel(args)
    stored = load_answers(dest, answers_rel)
    src = stored.get("_src_path")
    current = stored.get("_commit")
    latest = None
    update_available = False
    if src and Path(str(src)).exists() and is_git_repo(Path(str(src))):
        latest = newest_semver_tag(Path(str(src)).resolve()) or "HEAD"
        update_available = is_newer(latest, current)
    return success(
        {
            "ok": True,
            "command": "check-update",
            "current": current,
            "latest": latest,
            "update_available": update_available,
        }
    )


def is_newer(latest: str | None, current: Any) -> bool:
    if latest is None:
        return False
    if current == latest:
        return False
    latest_key = semver_key(str(latest))
    current_key = semver_key(str(current)) if current is not None else None
    if latest_key and current_key:
        return latest_key > current_key
    return latest != current


def command_update(args: argparse.Namespace) -> int:
    dest = Path(args.dest).resolve()
    answers_rel = answer_file_rel(args)
    stored = load_answers(dest, answers_rel)
    src = stored.get("_src_path")
    if not src:
        fail("answers file lacks _src_path")

    old_template = open_template(str(src), stored_ref=stored.get("_commit"))
    try:
        if old_template.is_git:
            new_template = open_template(str(src), args.vcs_ref)
        else:
            new_template = open_template(str(src))
        try:
            old_cfg = load_config(old_template.root)
            new_cfg = load_config(new_template.root)
            if (new_cfg.migrations or []) and not args.trust:
                fail("template migrations require --trust")
            if (new_cfg.tasks or []) and not (args.trust or args.skip_tasks):
                fail("template tasks require --trust or --skip-tasks")

            old_answers, _, _ = resolve_answers(old_cfg, existing=stored, cli_data=parse_data(args.data))
            new_answers, skipped_questions, secrets = resolve_answers(
                new_cfg, existing=stored, cli_data=parse_data(args.data)
            )
            old_plan = render_template_files(old_template.root, old_cfg, old_answers, dest, args.exclude, args.skip)
            new_plan = render_template_files(new_template.root, new_cfg, new_answers, dest, args.exclude, args.skip)

            writes: list[tuple[str, bytes]] = []
            conflicts: list[str] = []
            for rel, new_bytes in sorted(new_plan.files.items()):
                target = safe_dest_path(dest, rel)
                current_bytes = target.read_bytes() if target.exists() else None
                old_bytes = old_plan.files.get(rel)
                if current_bytes == new_bytes:
                    continue
                if current_bytes is None or current_bytes == old_bytes or args.overwrite:
                    writes.append((rel, new_bytes))
                    continue
                conflicts.append(rel)
                if args.conflict == "inline":
                    local_text = current_bytes.decode("utf-8", "replace")
                    template_text = new_bytes.decode("utf-8", "replace")
                    merged = (
                        "<<<<<<< local\n"
                        + local_text
                        + ("\n" if local_text and not local_text.endswith("\n") else "")
                        + "=======\n"
                        + template_text
                        + ("\n" if template_text and not template_text.endswith("\n") else "")
                        + ">>>>>>> template\n"
                    )
                    writes.append((rel, merged.encode("utf-8")))
                else:
                    writes.append((rel + ".rej", new_bytes))

            before, after = migration_actions(new_cfg)
            answers_bytes = dump_yaml(public_answers(new_template, new_answers, secrets, skipped_questions)).encode(
                "utf-8"
            )
            all_writes: list[tuple[str, bytes]] = []
            overlay: dict[str, bytes] = {}
            if args.trust:
                all_writes.extend(planned_action_writes(dest, before, overlay))
            all_writes.extend(writes)
            overlay.update(dict(writes))
            all_writes.append((answers_rel, answers_bytes))
            overlay[answers_rel] = answers_bytes
            if args.trust:
                all_writes.extend(planned_action_writes(dest, after, overlay))
            if not args.skip_tasks:
                all_writes.extend(planned_action_writes(dest, new_cfg.tasks or [], overlay))

            payload = {
                "ok": True,
                "command": "update",
                "operation": "update",
                "answers_file": answers_rel,
                "commit": new_template.commit,
                "written": sorted(rel for rel, _ in writes),
                "skipped": new_plan.skipped,
                "excluded": new_plan.excluded,
            }
            if conflicts:
                payload["conflicts"] = sorted(conflicts)
            if args.pretend:
                payload["pretend"] = True
                return success(payload)
            apply_writes(dest, all_writes)
            return success(payload)
        finally:
            new_template.close()
    finally:
        old_template.close()


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
    copy.add_argument("--exclude", action="append")
    copy.add_argument("--skip", action="append")
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
    recopy.add_argument("--exclude", action="append")
    recopy.add_argument("--skip", action="append")
    recopy.add_argument("--pretend", action="store_true")
    recopy.set_defaults(func=command_recopy)

    update = sub.add_parser("update")
    update.add_argument("dest")
    update.add_argument("--answers-file")
    update.add_argument("--vcs-ref")
    update.add_argument("--data", action="append")
    update.add_argument("--overwrite", action="store_true")
    update.add_argument("--skip-answered", action="store_true")
    update.add_argument("--exclude", action="append")
    update.add_argument("--skip", action="append")
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
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MiniError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

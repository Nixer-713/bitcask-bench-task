#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Tuple


FORMATS = "ipynb,py:percent"
ALT_FORMATS = "py:percent,ipynb"
STATE_NAME = ".minijupy-state.json"


class MiniJupyError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    root: Path
    config_path: Optional[Path] = None
    notebook_dir: Optional[PurePosixPath] = None
    script_dir: Optional[PurePosixPath] = None
    formats: str = FORMATS

    @property
    def has_dirs(self) -> bool:
        return self.notebook_dir is not None and self.script_dir is not None


@dataclass(frozen=True)
class PairPaths:
    ipynb_rel: str
    text_rel: str
    ipynb_abs: Path
    text_abs: Path


def resolve_user_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve(strict=False)


def normalize_rel(path: Path, root: Path) -> str:
    try:
        rel = path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise MiniJupyError(f"path mismatch: {path} is outside project root {root}") from exc
    text = rel.as_posix()
    if text == "." or text.startswith("../") or text == "..":
        raise MiniJupyError(f"path mismatch: {path}")
    return text


def display_path(path: Path, root: Path) -> str:
    try:
        return normalize_rel(path, root)
    except MiniJupyError:
        return path.as_posix()


def display_root(root: Path) -> str:
    cwd = Path.cwd().resolve(strict=False)
    try:
        rel = root.resolve(strict=False).relative_to(cwd)
        return rel.as_posix() if rel.as_posix() != "." else "."
    except ValueError:
        return root.as_posix()


def validate_rel_dir(value: str, key: str) -> PurePosixPath:
    rel = PurePosixPath(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise MiniJupyError(f"invalid config: {key} must be a relative path")
    if str(rel) in ("", "."):
        return PurePosixPath(".")
    return rel


def load_config(config_arg: Optional[str]) -> Config:
    if config_arg is None:
        return Config(root=Path.cwd().resolve(strict=False))

    config_path = resolve_user_path(config_arg)
    if not config_path.exists():
        raise MiniJupyError(f"invalid config: {config_arg} does not exist")
    if not config_path.is_file():
        raise MiniJupyError(f"invalid config: {config_arg} is not a file")

    values: Dict[str, str] = {}
    allowed = {"formats", "notebook_dir", "script_dir"}
    line_re = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"\s*$')
    for line_no, raw in enumerate(config_path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = line_re.match(stripped)
        if not match:
            raise MiniJupyError(f"invalid config: line {line_no}")
        key, value = match.group(1), match.group(2)
        if key not in allowed:
            raise MiniJupyError(f"invalid config: unknown key {key}")
        if key in values:
            raise MiniJupyError(f"invalid config: duplicate key {key}")
        values[key] = value

    formats = values.get("formats", FORMATS)
    if formats not in (FORMATS, ALT_FORMATS):
        raise MiniJupyError("invalid config: unsupported formats")

    has_notebooks = "notebook_dir" in values
    has_scripts = "script_dir" in values
    if has_notebooks != has_scripts:
        raise MiniJupyError("invalid config: notebook_dir and script_dir must be supplied together")

    notebook_dir = validate_rel_dir(values["notebook_dir"], "notebook_dir") if has_notebooks else None
    script_dir = validate_rel_dir(values["script_dir"], "script_dir") if has_scripts else None
    if notebook_dir is not None and script_dir is not None and notebook_dir == script_dir:
        raise MiniJupyError("invalid config: notebook_dir and script_dir must be different")

    return Config(
        root=config_path.parent.resolve(strict=False),
        config_path=config_path,
        notebook_dir=notebook_dir,
        script_dir=script_dir,
        formats=formats,
    )


def is_under(path: PurePosixPath, base: PurePosixPath) -> bool:
    if str(base) == ".":
        return True
    return len(path.parts) >= len(base.parts) and path.parts[: len(base.parts)] == base.parts


def relative_under(path: PurePosixPath, base: PurePosixPath) -> PurePosixPath:
    if str(base) == ".":
        return path
    if not is_under(path, base):
        raise MiniJupyError(f"path mismatch: {path} is outside {base}")
    remainder = path.parts[len(base.parts) :]
    return PurePosixPath(*remainder) if remainder else PurePosixPath(path.name)


def with_suffix_posix(path: PurePosixPath, suffix: str) -> PurePosixPath:
    return path.with_suffix(suffix)


def derive_pair_paths(input_arg: str, config: Config) -> PairPaths:
    input_abs = resolve_user_path(input_arg)
    rel = normalize_rel(input_abs, config.root)
    rel_path = PurePosixPath(rel)
    suffix = rel_path.suffix.lower()
    if suffix not in (".ipynb", ".py"):
        raise MiniJupyError("unsupported file type")

    if config.has_dirs:
        assert config.notebook_dir is not None
        assert config.script_dir is not None
        if suffix == ".ipynb":
            if not is_under(rel_path, config.notebook_dir):
                raise MiniJupyError("path mismatch: notebook is outside notebook_dir")
            nested = relative_under(rel_path, config.notebook_dir)
            ipynb_rel = rel_path
            text_rel = config.script_dir / with_suffix_posix(nested, ".py")
        else:
            if not is_under(rel_path, config.script_dir):
                raise MiniJupyError("path mismatch: script is outside script_dir")
            nested = relative_under(rel_path, config.script_dir)
            text_rel = rel_path
            ipynb_rel = config.notebook_dir / with_suffix_posix(nested, ".ipynb")
    else:
        if suffix == ".ipynb":
            ipynb_rel = rel_path
            text_rel = with_suffix_posix(rel_path, ".py")
        else:
            text_rel = rel_path
            ipynb_rel = with_suffix_posix(rel_path, ".ipynb")

    return PairPaths(
        ipynb_rel=ipynb_rel.as_posix(),
        text_rel=text_rel.as_posix(),
        ipynb_abs=config.root / Path(ipynb_rel.as_posix()),
        text_abs=config.root / Path(text_rel.as_posix()),
    )


def parse_version(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MiniJupyError(f"invalid version in {context}")
    return value


def parse_version_text(value: Optional[str], context: str) -> int:
    if value is None:
        return 1
    if not re.fullmatch(r"[0-9]+", value.strip()):
        raise MiniJupyError(f"invalid version in {context}")
    return int(value.strip())


def normalize_source(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "".join(value)
    raise MiniJupyError("invalid source")


def normalize_cell_metadata(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MiniJupyError("invalid cell metadata")
    out: Dict[str, Any] = {}
    if "tags" in value:
        tags = value["tags"]
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise MiniJupyError("invalid cell tags")
        out["tags"] = list(tags)
    if "name" in value:
        name = value["name"]
        if not isinstance(name, str):
            raise MiniJupyError("invalid cell name")
        out["name"] = name
    return out


def normalize_metadata(value: Any, context: str) -> Dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise MiniJupyError(f"invalid metadata in {context}")

    minijupy_in = value.get("minijupy", {})
    if minijupy_in is None:
        minijupy_in = {}
    if not isinstance(minijupy_in, dict):
        raise MiniJupyError(f"invalid minijupy metadata in {context}")

    minijupy: Dict[str, Any] = {"version": parse_version(minijupy_in.get("version", 1), context)}
    if "formats" in minijupy_in:
        formats = minijupy_in["formats"]
        if not isinstance(formats, str) or formats not in (FORMATS, ALT_FORMATS):
            raise MiniJupyError(f"invalid formats in {context}")
        minijupy["formats"] = formats

    kernelspec: Dict[str, Any] = {}
    kernelspec_in = value.get("kernelspec", {})
    if isinstance(kernelspec_in, dict) and isinstance(kernelspec_in.get("name"), str):
        kernelspec["name"] = kernelspec_in["name"]

    language_info: Dict[str, Any] = {}
    language_in = value.get("language_info", {})
    if isinstance(language_in, dict):
        language_info = copy.deepcopy(language_in)

    return {"kernelspec": kernelspec, "language_info": language_info, "minijupy": minijupy}


def normalize_notebook_obj(obj: Any, context: str) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise MiniJupyError(f"malformed notebook: {context}")
    if obj.get("nbformat") != 4:
        raise MiniJupyError("unsupported notebook nbformat")

    nbformat_minor = obj.get("nbformat_minor", 5)
    if not isinstance(nbformat_minor, int) or isinstance(nbformat_minor, bool):
        nbformat_minor = 5

    cells_in = obj.get("cells", [])
    if not isinstance(cells_in, list):
        raise MiniJupyError("malformed notebook cells")

    cells: List[Dict[str, Any]] = []
    seen_ids = set()
    for index, cell_in in enumerate(cells_in, 1):
        if not isinstance(cell_in, dict):
            raise MiniJupyError("malformed notebook cell")
        cell_type = cell_in.get("cell_type")
        if cell_type not in ("code", "markdown", "raw"):
            raise MiniJupyError(f"unsupported cell type: {cell_type}")
        cell_id = cell_in.get("id", f"c{index}")
        if not isinstance(cell_id, str):
            raise MiniJupyError("invalid cell id")
        if cell_id in seen_ids:
            raise MiniJupyError(f"duplicate cell id: {cell_id}")
        seen_ids.add(cell_id)

        cell: Dict[str, Any] = {
            "id": cell_id,
            "cell_type": cell_type,
            "source": normalize_source(cell_in.get("source", "")),
            "metadata": normalize_cell_metadata(cell_in.get("metadata", {})),
        }
        if cell_type == "code":
            outputs = cell_in.get("outputs", [])
            if outputs is None:
                outputs = []
            if not isinstance(outputs, list):
                raise MiniJupyError("invalid outputs")
            cell["execution_count"] = cell_in.get("execution_count")
            cell["outputs"] = copy.deepcopy(outputs)
        cells.append(cell)

    return {
        "nbformat": 4,
        "nbformat_minor": nbformat_minor,
        "metadata": normalize_metadata(obj.get("metadata", {}), context),
        "cells": cells,
    }


def read_ipynb(path: Path) -> Dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed JSON notebook: {path}") from exc
    return normalize_notebook_obj(obj, path.as_posix())


def parse_header(lines: List[str]) -> Tuple[Dict[str, Any], int]:
    if not lines or lines[0].strip() != "# ---":
        return {}, 0

    metadata: Dict[str, Any] = {}
    minijupy: Dict[str, Any] = {}
    kernelspec: Dict[str, Any] = {}
    section: Optional[str] = None
    index = 1
    while index < len(lines):
        raw = lines[index]
        if raw.strip() == "# ---":
            if minijupy:
                metadata["minijupy"] = minijupy
            if kernelspec:
                metadata["kernelspec"] = kernelspec
            return metadata, index + 1
        if not raw.startswith("#"):
            raise MiniJupyError("malformed percent header")
        content = raw[1:]
        if content.startswith(" "):
            content = content[1:]
        content_no_newline = content.rstrip("\r\n")
        if not content_no_newline.strip():
            index += 1
            continue
        if not content_no_newline.startswith("  ") and content_no_newline.endswith(":"):
            section = content_no_newline[:-1].strip()
            index += 1
            continue
        if content_no_newline.startswith("  "):
            if section not in ("minijupy", "kernelspec"):
                index += 1
                continue
            nested = content_no_newline[2:]
            if ":" not in nested:
                index += 1
                continue
            key, value = nested.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"')
            if section == "minijupy" and key == "formats":
                minijupy["formats"] = value
            elif section == "minijupy" and key == "version":
                minijupy["version"] = parse_version_text(value, "percent header")
            elif section == "kernelspec" and key == "name":
                kernelspec["name"] = value
        index += 1

    raise MiniJupyError("malformed percent header")


def parse_marker(line: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    if not line.startswith("# %%"):
        return None
    rest = line[len("# %%") :].strip()
    cell_type = "code"
    if rest.startswith("["):
        end = rest.find("]")
        if end < 0:
            raise MiniJupyError("malformed percent marker")
        marker_type = rest[1:end].strip()
        if marker_type in ("markdown", "md"):
            cell_type = "markdown"
        elif marker_type == "raw":
            cell_type = "raw"
        else:
            raise MiniJupyError("unsupported percent marker type")
        rest = rest[end + 1 :].strip()

    metadata: Dict[str, Any] = {}
    if rest:
        try:
            metadata = json.loads(rest)
        except json.JSONDecodeError as exc:
            raise MiniJupyError("malformed percent marker JSON") from exc
        if not isinstance(metadata, dict):
            raise MiniJupyError("malformed percent marker JSON")
        unknown = set(metadata) - {"id", "tags", "name"}
        if unknown:
            raise MiniJupyError("unsupported percent marker metadata")
        metadata = normalize_cell_metadata(metadata)
        if "id" in json.loads(rest):
            original = json.loads(rest)
            cell_id = original.get("id")
            if not isinstance(cell_id, str):
                raise MiniJupyError("invalid cell id")
            metadata["id"] = cell_id
    return cell_type, metadata


def markdown_body(lines: List[str]) -> str:
    out: List[str] = []
    for line in lines:
        if line.startswith("# "):
            out.append(line[2:])
        else:
            out.append(line)
    return "".join(out)


def parse_percent_text(text: str, context: str = "percent script") -> Dict[str, Any]:
    lines = text.splitlines(True)
    header_metadata, start = parse_header(lines)
    body_lines = lines[start:]

    cells_raw: List[Dict[str, Any]] = []
    pre_marker: List[str] = []
    current_type: Optional[str] = None
    current_meta: Dict[str, Any] = {}
    current_body: List[str] = []

    def finish_current() -> None:
        nonlocal current_type, current_meta, current_body
        if current_type is None:
            return
        source = markdown_body(current_body) if current_type == "markdown" else "".join(current_body)
        cell = {
            "cell_type": current_type,
            "source": source,
            "metadata": {k: v for k, v in current_meta.items() if k in ("tags", "name")},
        }
        if "id" in current_meta:
            cell["id"] = current_meta["id"]
        cells_raw.append(cell)
        current_type = None
        current_meta = {}
        current_body = []

    def finish_implicit_if_needed() -> None:
        nonlocal pre_marker
        if any(line.strip() for line in pre_marker):
            cells_raw.append({
                "cell_type": "code",
                "source": "".join(pre_marker),
                "metadata": {},
            })
        pre_marker = []

    for line in body_lines:
        marker = parse_marker(line)
        if marker is not None:
            if current_type is None:
                finish_implicit_if_needed()
            else:
                finish_current()
            current_type, current_meta = marker
            current_body = []
        else:
            if current_type is None:
                pre_marker.append(line)
            else:
                current_body.append(line)

    if current_type is None:
        finish_implicit_if_needed()
    else:
        finish_current()

    minijupy_in = header_metadata.get("minijupy", {})
    if "version" not in minijupy_in:
        minijupy_in["version"] = 1
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": header_metadata.get("kernelspec", {}),
            "language_info": {},
            "minijupy": minijupy_in,
        },
        "cells": cells_raw,
    }
    return normalize_notebook_obj(notebook, context)


def read_percent(path: Path) -> Dict[str, Any]:
    return parse_percent_text(path.read_text(encoding="utf-8"), path.as_posix())


def notebook_version(nb: Dict[str, Any]) -> int:
    return parse_version(nb["metadata"]["minijupy"].get("version", 1), "notebook")


def notebook_format(nb: Dict[str, Any]) -> Optional[str]:
    value = nb["metadata"]["minijupy"].get("formats")
    return value if isinstance(value, str) else None


def ensure_formats(nb: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(nb)
    out.setdefault("metadata", {}).setdefault("minijupy", {})["formats"] = FORMATS
    out["metadata"]["minijupy"]["version"] = notebook_version(out)
    return out


def marker_json(cell: Dict[str, Any]) -> str:
    meta: Dict[str, Any] = {}
    if cell.get("id"):
        meta["id"] = cell["id"]
    cell_meta = cell.get("metadata", {})
    if "tags" in cell_meta:
        meta["tags"] = cell_meta["tags"]
    if "name" in cell_meta:
        meta["name"] = cell_meta["name"]
    return " " + json.dumps(meta, sort_keys=True, separators=(", ", ": ")) if meta else ""


def write_markdown_source(source: str) -> str:
    if not source:
        return ""
    parts = source.splitlines(True)
    if source and not parts:
        parts = [source]
    return "".join("# " + part for part in parts)


def write_percent(nb: Dict[str, Any]) -> str:
    lines: List[str] = ["# ---\n", "# minijupy:\n"]
    minijupy = nb["metadata"]["minijupy"]
    if "formats" in minijupy:
        lines.append(f"#   formats: {minijupy['formats']}\n")
    lines.append(f"#   version: {notebook_version(nb)}\n")
    kernelspec = nb["metadata"].get("kernelspec", {})
    if isinstance(kernelspec, dict) and isinstance(kernelspec.get("name"), str):
        lines.append("# kernelspec:\n")
        lines.append(f"#   name: {kernelspec['name']}\n")
    lines.append("# ---\n")

    for index, cell in enumerate(nb["cells"]):
        cell_type = cell["cell_type"]
        if cell_type == "code":
            marker = "# %%"
        elif cell_type == "markdown":
            marker = "# %% [markdown]"
        elif cell_type == "raw":
            marker = "# %% [raw]"
        else:
            raise MiniJupyError("unsupported cell type")
        lines.append(marker + marker_json(cell) + "\n")
        source = cell.get("source", "")
        if cell_type == "markdown":
            body = write_markdown_source(source)
        else:
            body = source
        lines.append(body)
        if body and not body.endswith("\n") and index < len(nb["cells"]) - 1:
            lines.append("\n")
    return "".join(lines)


def notebook_json(nb: Dict[str, Any]) -> str:
    return json.dumps(nb, indent=2, ensure_ascii=False) + "\n"


def canonical_hash(nb: Dict[str, Any]) -> str:
    encoded = json.dumps(nb, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def source_hash(cell: Dict[str, Any]) -> str:
    return hashlib.sha256(cell.get("source", "").encode("utf-8")).hexdigest()


def preserve_outputs(new_nb: Dict[str, Any], old_nb: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(new_nb)
    old_cells = old_nb.get("cells", [])
    used = set()

    for new_index, new_cell in enumerate(out["cells"]):
        if new_cell["cell_type"] != "code":
            continue
        match_index: Optional[int] = None

        new_id = new_cell.get("id")
        if new_id is not None:
            for old_index, old_cell in enumerate(old_cells):
                if old_index in used:
                    continue
                if old_cell.get("cell_type") == "code" and old_cell.get("id") == new_id:
                    match_index = old_index
                    break

        if match_index is None:
            new_source_hash = source_hash(new_cell)
            for old_index, old_cell in enumerate(old_cells):
                if old_index in used:
                    continue
                if old_cell.get("cell_type") == "code" and source_hash(old_cell) == new_source_hash:
                    match_index = old_index
                    break

        if match_index is None and new_index < len(old_cells):
            old_cell = old_cells[new_index]
            if new_index not in used and old_cell.get("cell_type") == "code":
                match_index = new_index

        if match_index is not None:
            used.add(match_index)
            old_cell = old_cells[match_index]
            new_cell["execution_count"] = old_cell.get("execution_count")
            new_cell["outputs"] = copy.deepcopy(old_cell.get("outputs", []))
        else:
            new_cell["execution_count"] = None
            new_cell["outputs"] = []
    return out


def state_path(config: Config) -> Path:
    return config.root / STATE_NAME


def read_state(config: Config) -> Dict[str, Any]:
    path = state_path(config)
    if not path.exists():
        return {"pairs": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MiniJupyError("malformed state file") from exc
    if not isinstance(state, dict):
        raise MiniJupyError("malformed state file")
    pairs = state.get("pairs", {})
    if not isinstance(pairs, dict):
        raise MiniJupyError("malformed state file")
    return {"pairs": pairs}


def state_json(state: Dict[str, Any]) -> str:
    pairs = state.get("pairs", {})
    ordered = {"pairs": {key: pairs[key] for key in sorted(pairs)}}
    return json.dumps(ordered, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def update_state_entry(state: Dict[str, Any], paths: PairPaths, ip_nb: Dict[str, Any], text_nb: Dict[str, Any]) -> None:
    state.setdefault("pairs", {})[paths.ipynb_rel] = {
        "ipynb": paths.ipynb_rel,
        "text": paths.text_rel,
        "last_synced": {
            "ipynb_version": notebook_version(ip_nb),
            "text_version": notebook_version(text_nb),
            "ipynb_hash": canonical_hash(ip_nb),
            "text_hash": canonical_hash(text_nb),
        },
    }


def last_versions(state_entry: Optional[Dict[str, Any]]) -> Tuple[Optional[int], Optional[int]]:
    if not isinstance(state_entry, dict):
        return None, None
    last = state_entry.get("last_synced", {})
    if not isinstance(last, dict):
        return None, None
    ip = last.get("ipynb_version")
    text = last.get("text_version")
    return (ip if isinstance(ip, int) and not isinstance(ip, bool) else None,
            text if isinstance(text, int) and not isinstance(text, bool) else None)


def compare_public(ip_nb: Optional[Dict[str, Any]], text_nb: Optional[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    differences: List[str] = []
    if ip_nb is None or text_nb is None:
        return False, ["missing"]
    if notebook_version(ip_nb) != notebook_version(text_nb):
        differences.append("version")
    if notebook_format(ip_nb) != notebook_format(text_nb):
        differences.append("formats")
    ip_cells = ip_nb["cells"]
    text_cells = text_nb["cells"]
    if len(ip_cells) != len(text_cells):
        differences.append("cell_count")
    for ip_cell, text_cell in zip(ip_cells, text_cells):
        if ip_cell.get("cell_type") != text_cell.get("cell_type"):
            differences.append("cell_type")
        if ip_cell.get("source") != text_cell.get("source"):
            differences.append("source")
        if ip_cell.get("id") != text_cell.get("id"):
            differences.append("id")
        ip_meta = ip_cell.get("metadata", {})
        text_meta = text_cell.get("metadata", {})
        if ip_meta.get("tags", []) != text_meta.get("tags", []):
            differences.append("tags")
        if ip_meta.get("name") != text_meta.get("name"):
            differences.append("name")
    unique = []
    for item in differences:
        if item not in unique:
            unique.append(item)
    return not unique, unique


def planned_writes_for(source: str, paths: PairPaths) -> List[str]:
    if source == "ipynb":
        return [paths.text_rel, STATE_NAME]
    if source == "text":
        return [paths.ipynb_rel, STATE_NAME]
    return []


def pair_info(paths: PairPaths, config: Config, state: Dict[str, Any], command: str,
              explicit_source: Optional[str] = None) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]], bool]:
    ip_exists = paths.ipynb_abs.exists()
    text_exists = paths.text_abs.exists()
    if not ip_exists and not text_exists:
        raise MiniJupyError("both sides of pair are missing")

    ip_nb = read_ipynb(paths.ipynb_abs) if ip_exists else None
    text_nb = read_percent(paths.text_abs) if text_exists else None
    ip_ver = notebook_version(ip_nb) if ip_nb is not None else None
    text_ver = notebook_version(text_nb) if text_nb is not None else None

    entry = state.get("pairs", {}).get(paths.ipynb_rel)
    last_ip, last_text = last_versions(entry)
    has_state = entry is not None and last_ip is not None and last_text is not None

    conflict = False
    source = "none"
    if explicit_source is not None:
        if explicit_source == "ipynb" and not ip_exists:
            raise MiniJupyError("selected ipynb source is missing")
        if explicit_source == "text" and not text_exists:
            raise MiniJupyError("selected text source is missing")
        source = explicit_source
    elif ip_exists and not text_exists:
        source = "ipynb"
    elif text_exists and not ip_exists:
        source = "text"
    elif ip_exists and text_exists and has_state:
        ip_changed = ip_ver is not None and last_ip is not None and ip_ver > last_ip
        text_changed = text_ver is not None and last_text is not None and text_ver > last_text
        conflict = ip_changed and text_changed
        if conflict:
            source = "none"
        elif ip_changed:
            source = "ipynb"
        elif text_changed:
            source = "text"
        else:
            source = "none"
    else:
        source = "none"

    roundtrip_ok, differences = compare_public(ip_nb, text_nb)
    if has_state:
        if ip_ver is not None and last_ip is not None and last_ip > ip_ver:
            differences.append("state")
        if text_ver is not None and last_text is not None and last_text > text_ver:
            differences.append("state")
    differences = list(dict.fromkeys(differences))
    if differences:
        roundtrip_ok = False

    missing = []
    if not ip_exists:
        missing.append(paths.ipynb_rel)
    if not text_exists:
        missing.append(paths.text_rel)

    obj = {
        "ipynb": paths.ipynb_rel,
        "text": paths.text_rel,
        "exists": {"ipynb": ip_exists, "text": text_exists},
        "versions": {
            "ipynb": ip_ver,
            "text": text_ver,
            "last_ipynb": last_ip,
            "last_text": last_text,
        },
        "source": source if not conflict else "none",
        "conflict": conflict if explicit_source is None else False,
        "missing": missing,
        "planned_writes": planned_writes_for(source if not conflict else "none", paths),
        "roundtrip_ok": roundtrip_ok,
        "differences": differences,
        "errors": [],
    }
    return obj, ip_nb, text_nb, has_state


def status_document(command: str, config: Config, pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "ok": True,
        "command": command,
        "root": display_root(config.root),
        "pairs": pairs,
        "summary": {
            "pairs": len(pairs),
            "conflicts": sum(1 for pair in pairs if pair.get("conflict")),
            "missing": sum(len(pair.get("missing", [])) for pair in pairs),
            "planned_writes": sum(len(pair.get("planned_writes", [])) for pair in pairs),
            "errors": sum(len(pair.get("errors", [])) for pair in pairs),
        },
    }


def atomic_write_many(writes: Dict[Path, str]) -> None:
    if not writes:
        return
    temp_paths: List[Tuple[Path, Path]] = []
    try:
        for final_path, content in writes.items():
            final_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f".{final_path.name}.", suffix=".tmp", dir=final_path.parent)
            temp_path = Path(temp_name)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
            temp_paths.append((temp_path, final_path))
        for temp_path, final_path in temp_paths:
            os.replace(temp_path, final_path)
    except Exception:
        for temp_path, _ in temp_paths:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
        raise


def command_inspect(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_config(args.config)
    path = resolve_user_path(args.input)
    suffix = path.suffix.lower()
    if suffix == ".ipynb":
        nb = read_ipynb(path)
        fmt = "ipynb"
    elif suffix == ".py":
        nb = read_percent(path)
        fmt = "py:percent"
    else:
        raise MiniJupyError("unsupported file type")
    return {
        "ok": True,
        "command": "inspect",
        "path": display_path(path, config.root),
        "format": fmt,
        "version": notebook_version(nb),
        "notebook": nb,
    }


def command_paths(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_config(args.config)
    paths = derive_pair_paths(args.input, config)
    return {
        "ok": True,
        "command": "paths",
        "root": display_root(config.root),
        "input": display_path(resolve_user_path(args.input), config.root),
        "ipynb": paths.ipynb_rel,
        "text": paths.text_rel,
        "exists": {"ipynb": paths.ipynb_abs.exists(), "text": paths.text_abs.exists()},
    }


def command_to_text(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_config(args.config)
    input_path = resolve_user_path(args.input)
    output_path = resolve_user_path(args.output)
    if input_path.suffix.lower() != ".ipynb":
        raise MiniJupyError("to-text input must be .ipynb")
    if output_path.suffix.lower() != ".py":
        raise MiniJupyError("to-text output must be .py")
    nb = read_ipynb(input_path)
    atomic_write_many({output_path: write_percent(nb)})
    return {
        "ok": True,
        "command": "to-text",
        "input": display_path(input_path, config.root),
        "output": display_path(output_path, config.root),
        "version": notebook_version(nb),
    }


def command_to_ipynb(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_config(args.config)
    input_path = resolve_user_path(args.input)
    output_path = resolve_user_path(args.output)
    if input_path.suffix.lower() != ".py":
        raise MiniJupyError("to-ipynb input must be .py")
    if output_path.suffix.lower() != ".ipynb":
        raise MiniJupyError("to-ipynb output must be .ipynb")
    nb = read_percent(input_path)
    if args.update and output_path.exists():
        nb = preserve_outputs(nb, read_ipynb(output_path))
    atomic_write_many({output_path: notebook_json(nb)})
    return {
        "ok": True,
        "command": "to-ipynb",
        "input": display_path(input_path, config.root),
        "output": display_path(output_path, config.root),
        "version": notebook_version(nb),
    }


def command_pair(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_config(args.config)
    paths = derive_pair_paths(args.input, config)
    ip_exists = paths.ipynb_abs.exists()
    text_exists = paths.text_abs.exists()
    if not ip_exists and not text_exists:
        raise MiniJupyError("both sides of pair are missing")

    writes: Dict[Path, str] = {}
    state = read_state(config)

    if ip_exists:
        ip_nb = ensure_formats(read_ipynb(paths.ipynb_abs))
    else:
        ip_nb = ensure_formats(read_percent(paths.text_abs))

    if text_exists:
        text_nb = ensure_formats(read_percent(paths.text_abs))
    else:
        text_nb = ensure_formats(copy.deepcopy(ip_nb))

    writes[paths.ipynb_abs] = notebook_json(ip_nb)
    writes[paths.text_abs] = write_percent(text_nb)
    parsed_text_after_write = parse_percent_text(writes[paths.text_abs], paths.text_rel)
    update_state_entry(state, paths, ip_nb, parsed_text_after_write)
    writes[state_path(config)] = state_json(state)
    atomic_write_many(writes)

    pair_obj, _, _, _ = pair_info(paths, config, read_state(config), "pair")
    pair_obj["planned_writes"] = [display_path(path, config.root) for path in writes]
    return {
        "ok": True,
        "command": "pair",
        "root": display_root(config.root),
        "pair": pair_obj,
    }


def discover_pairs(config: Config) -> List[PairPaths]:
    search_roots: List[Path]
    if config.has_dirs:
        assert config.notebook_dir is not None and config.script_dir is not None
        search_roots = [config.root / Path(config.notebook_dir.as_posix()), config.root / Path(config.script_dir.as_posix())]
    else:
        search_roots = [config.root]

    discovered: Dict[str, PairPaths] = {}
    text_to_ipynb: Dict[str, str] = {}
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in sorted(search_root.rglob("*")):
            if not path.is_file() or path.name == STATE_NAME:
                continue
            if path.suffix.lower() not in (".ipynb", ".py"):
                continue
            pair = derive_pair_paths(path.as_posix(), config)
            if pair.ipynb_rel in discovered and discovered[pair.ipynb_rel].text_rel != pair.text_rel:
                raise MiniJupyError("duplicate paired paths")
            if pair.text_rel in text_to_ipynb and text_to_ipynb[pair.text_rel] != pair.ipynb_rel:
                raise MiniJupyError("duplicate paired paths")
            discovered[pair.ipynb_rel] = pair
            text_to_ipynb[pair.text_rel] = pair.ipynb_rel
    return [discovered[key] for key in sorted(discovered)]


def status_or_check(args: argparse.Namespace, command: str) -> Dict[str, Any]:
    config = load_config(args.config)
    if args.all:
        if args.config is None:
            raise MiniJupyError("--all requires --config")
        pairs_paths = discover_pairs(config)
    else:
        if not args.input:
            raise MiniJupyError("--input is required")
        pairs_paths = [derive_pair_paths(args.input, config)]

    state = read_state(config)
    pairs = [pair_info(paths, config, state, command)[0] for paths in pairs_paths]
    return status_document(command, config, pairs)


def sync_file_writes(paths: PairPaths, config: Config, state: Dict[str, Any],
                     source: str) -> Tuple[Dict[Path, str], Dict[str, Any]]:
    writes: Dict[Path, str] = {}
    if source == "none":
        return writes, state

    if source == "ipynb":
        ip_nb = read_ipynb(paths.ipynb_abs)
        text_content = write_percent(ip_nb)
        text_nb = parse_percent_text(text_content, paths.text_rel)
        writes[paths.text_abs] = text_content
    elif source == "text":
        text_nb = read_percent(paths.text_abs)
        ip_nb = copy.deepcopy(text_nb)
        if paths.ipynb_abs.exists():
            ip_nb = preserve_outputs(ip_nb, read_ipynb(paths.ipynb_abs))
        writes[paths.ipynb_abs] = notebook_json(ip_nb)
    else:
        raise MiniJupyError("invalid source")

    update_state_entry(state, paths, ip_nb, text_nb)
    return writes, state


def sync_one(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_config(args.config)
    paths = derive_pair_paths(args.input, config)
    state = read_state(config)
    pair_obj, _, _, has_state = pair_info(paths, config, state, "sync", args.source)

    if args.source is None and pair_obj["conflict"]:
        raise MiniJupyError("conflict without explicit source")
    if args.source is None and pair_obj["exists"]["ipynb"] and pair_obj["exists"]["text"] and not has_state:
        raise MiniJupyError("pair has no state; run pair or use --source")

    source = pair_obj["source"]
    writes, new_state = sync_file_writes(paths, config, copy.deepcopy(state), source)
    if writes:
        writes[state_path(config)] = state_json(new_state)
    pair_obj["planned_writes"] = [display_path(path, config.root) for path in writes]
    atomic_write_many(writes)
    return status_document("sync", config, [pair_obj])


def sync_all(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_config(args.config)
    if args.config is None:
        raise MiniJupyError("--all requires --config")
    pairs_paths = discover_pairs(config)
    state = read_state(config)
    working_state = copy.deepcopy(state)
    all_writes: Dict[Path, str] = {}
    pair_objects: List[Dict[str, Any]] = []
    wrote_any = False

    for paths in pairs_paths:
        pair_obj, _, _, has_state = pair_info(paths, config, working_state, "sync", args.source)
        if args.source is None and pair_obj["conflict"]:
            raise MiniJupyError("conflict without explicit source")
        if args.source is None and pair_obj["exists"]["ipynb"] and pair_obj["exists"]["text"] and not has_state:
            raise MiniJupyError("pair has no state; run pair or use --source")
        writes, working_state = sync_file_writes(paths, config, working_state, pair_obj["source"])
        if writes:
            wrote_any = True
        for path, content in writes.items():
            if path in all_writes:
                raise MiniJupyError("duplicate paired paths")
            all_writes[path] = content
        pair_obj["planned_writes"] = [display_path(path, config.root) for path in writes]
        if writes:
            pair_obj["planned_writes"].append(STATE_NAME)
        pair_objects.append(pair_obj)

    if wrote_any:
        all_writes[state_path(config)] = state_json(working_state)
    atomic_write_many(all_writes)
    return status_document("sync", config, pair_objects)


def command_sync(args: argparse.Namespace) -> Dict[str, Any]:
    if args.all:
        return sync_all(args)
    if not args.input:
        raise MiniJupyError("--input is required")
    return sync_one(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minijupy.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_p = subparsers.add_parser("inspect")
    inspect_p.add_argument("--input", required=True)
    inspect_p.add_argument("--config")

    paths_p = subparsers.add_parser("paths")
    paths_p.add_argument("--input", required=True)
    paths_p.add_argument("--config")

    to_text_p = subparsers.add_parser("to-text")
    to_text_p.add_argument("--input", required=True)
    to_text_p.add_argument("--output", required=True)
    to_text_p.add_argument("--config")

    to_ipynb_p = subparsers.add_parser("to-ipynb")
    to_ipynb_p.add_argument("--input", required=True)
    to_ipynb_p.add_argument("--output", required=True)
    to_ipynb_p.add_argument("--config")
    to_ipynb_p.add_argument("--update", action="store_true")

    pair_p = subparsers.add_parser("pair")
    pair_p.add_argument("--input", required=True)
    pair_p.add_argument("--config")

    for name in ("status", "check"):
        command_p = subparsers.add_parser(name)
        command_p.add_argument("--input")
        command_p.add_argument("--all", action="store_true")
        command_p.add_argument("--config")

    sync_p = subparsers.add_parser("sync")
    sync_p.add_argument("--input")
    sync_p.add_argument("--all", action="store_true")
    sync_p.add_argument("--config")
    sync_p.add_argument("--source", choices=["ipynb", "text"])
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if getattr(args, "all", False) and getattr(args, "input", None):
            raise MiniJupyError("use either --input or --all, not both")
        if args.command == "inspect":
            result = command_inspect(args)
        elif args.command == "paths":
            result = command_paths(args)
        elif args.command == "to-text":
            result = command_to_text(args)
        elif args.command == "to-ipynb":
            result = command_to_ipynb(args)
        elif args.command == "pair":
            result = command_pair(args)
        elif args.command == "status":
            result = status_or_check(args, "status")
        elif args.command == "check":
            result = status_or_check(args, "check")
        elif args.command == "sync":
            result = command_sync(args)
        else:
            raise MiniJupyError("unsupported command")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except MiniJupyError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

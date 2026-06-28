#!/usr/bin/env python3
"""MiniJupy: a small deterministic paired-notebook CLI."""

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


CANONICAL_FORMATS = "ipynb,py:percent"
ALLOWED_CONFIG_FORMATS = {"ipynb,py:percent", "py:percent,ipynb"}
STATE_NAME = ".minijupy-state.json"


class MiniJupyError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    root: Path
    path: Path | None
    formats: str | None
    notebook_dir: str | None
    script_dir: str | None

    @property
    def has_dirs(self) -> bool:
        return self.notebook_dir is not None and self.script_dir is not None


@dataclass(frozen=True)
class PairPaths:
    ipynb_rel: str
    text_rel: str
    ipynb_abs: Path
    text_abs: Path


def fail(message: str) -> None:
    raise MiniJupyError(message)


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"file not found: {path}")
    except OSError as exc:
        fail(f"cannot read {path}: {exc}")


def parse_json_text(text: str, label: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        fail(f"malformed JSON {label}: {exc.msg}")


def normalized_rel(path: Path, root: Path) -> str:
    root_resolved = root.resolve(strict=False)
    full = path if path.is_absolute() else root / path
    try:
        rel = full.resolve(strict=False).relative_to(root_resolved)
    except ValueError:
        fail(f"path mismatch: {path}")
    return rel.as_posix()


def abs_from_rel(root: Path, rel: str) -> Path:
    return root / Path(rel)


def display_root(root: Path) -> str:
    cwd = Path.cwd().resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    if root_resolved == cwd:
        return "."
    try:
        rel = root_resolved.relative_to(cwd)
        return rel.as_posix() or "."
    except ValueError:
        return root_resolved.as_posix()


def parse_config(config_arg: str | None) -> Config:
    if config_arg is None:
        return Config(Path.cwd().resolve(strict=False), None, None, None, None)

    config_path = Path(config_arg)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    config_path = config_path.resolve(strict=False)
    if not config_path.exists():
        fail(f"invalid config: file not found: {config_arg}")

    values: dict[str, str] = {}
    line_re = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"\s*(?:#.*)?$')
    for number, raw in enumerate(read_text_file(config_path).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = line_re.match(line)
        if not match:
            fail(f"invalid config line {number}")
        key, value = match.groups()
        if key not in {"formats", "notebook_dir", "script_dir"}:
            fail(f"invalid config key: {key}")
        if key in values:
            fail(f"invalid config duplicate key: {key}")
        values[key] = value

    formats = values.get("formats")
    if formats is not None and formats not in ALLOWED_CONFIG_FORMATS:
        fail("invalid config: unsupported formats")

    notebook_dir = values.get("notebook_dir")
    script_dir = values.get("script_dir")
    if (notebook_dir is None) != (script_dir is None):
        fail("invalid config: notebook_dir and script_dir must be supplied together")

    def clean_dir(value: str | None, key: str) -> str | None:
        if value is None:
            return None
        p = PurePosixPath(value.replace(os.sep, "/"))
        if p.is_absolute() or ".." in p.parts or not p.as_posix() or p.as_posix() == ".":
            fail(f"invalid config: {key}")
        return p.as_posix().rstrip("/")

    return Config(
        root=config_path.parent.resolve(strict=False),
        path=config_path,
        formats=formats,
        notebook_dir=clean_dir(notebook_dir, "notebook_dir"),
        script_dir=clean_dir(script_dir, "script_dir"),
    )


def parse_version(value, label: str) -> int:
    if value is None:
        return 1
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        fail(f"invalid version in {label}")
    return value


def parse_header_version(value: str | None, label: str) -> int:
    if value is None:
        return 1
    try:
        parsed = int(value)
    except ValueError:
        fail(f"invalid version in {label}")
    if parsed < 0:
        fail(f"invalid version in {label}")
    return parsed


def source_to_string(source) -> str:
    if source is None:
        return ""
    if isinstance(source, str):
        return source
    if isinstance(source, list) and all(isinstance(part, str) for part in source):
        return "".join(source)
    fail("invalid cell source")


def clean_cell_metadata(metadata) -> dict:
    if not isinstance(metadata, dict):
        metadata = {}
    clean: dict = {}
    tags = metadata.get("tags")
    if isinstance(tags, list) and all(isinstance(tag, str) for tag in tags):
        clean["tags"] = list(tags)
    name = metadata.get("name")
    if isinstance(name, str):
        clean["name"] = name
    return clean


def normalize_notebook_obj(obj, label: str = "notebook") -> dict:
    if not isinstance(obj, dict):
        fail(f"malformed {label}: expected object")
    if obj.get("nbformat") != 4:
        fail("unsupported notebook nbformat")

    nbformat_minor = obj.get("nbformat_minor", 5)
    if isinstance(nbformat_minor, bool) or not isinstance(nbformat_minor, int):
        nbformat_minor = 5

    raw_metadata = obj.get("metadata", {})
    if not isinstance(raw_metadata, dict):
        raw_metadata = {}
    raw_minijupy = raw_metadata.get("minijupy", {})
    if not isinstance(raw_minijupy, dict):
        raw_minijupy = {}
    version = parse_version(raw_minijupy.get("version", 1), label)
    formats = raw_minijupy.get("formats")
    if formats is not None and not isinstance(formats, str):
        fail("invalid formats metadata")

    kernelspec = raw_metadata.get("kernelspec", {})
    if not isinstance(kernelspec, dict):
        kernelspec = {}
    language_info = raw_metadata.get("language_info", {})
    if not isinstance(language_info, dict):
        language_info = {}

    mini: dict = {}
    if formats is not None:
        mini["formats"] = formats
    mini["version"] = version

    cells_in = obj.get("cells", [])
    if not isinstance(cells_in, list):
        fail("malformed notebook cells")
    cells: list[dict] = []
    ids: set[str] = set()
    for index, raw_cell in enumerate(cells_in, start=1):
        if not isinstance(raw_cell, dict):
            fail("malformed notebook cell")
        cell_type = raw_cell.get("cell_type", "code")
        if cell_type not in {"code", "markdown", "raw"}:
            fail(f"unsupported cell type: {cell_type}")
        cell_id = raw_cell.get("id")
        if cell_id is None:
            cell_id = f"c{index}"
        if not isinstance(cell_id, str):
            fail("invalid cell id")
        if cell_id in ids:
            fail(f"duplicate cell id: {cell_id}")
        ids.add(cell_id)
        cell = {
            "id": cell_id,
            "cell_type": cell_type,
            "source": source_to_string(raw_cell.get("source", "")),
            "metadata": clean_cell_metadata(raw_cell.get("metadata", {})),
        }
        if cell_type == "code":
            cell["execution_count"] = raw_cell.get("execution_count", None)
            outputs = raw_cell.get("outputs", [])
            cell["outputs"] = copy.deepcopy(outputs if isinstance(outputs, list) else [])
        cells.append(cell)

    return {
        "nbformat": 4,
        "nbformat_minor": nbformat_minor,
        "metadata": {
            "kernelspec": copy.deepcopy(kernelspec),
            "language_info": copy.deepcopy(language_info),
            "minijupy": mini,
        },
        "cells": cells,
    }


def read_ipynb(path: Path) -> dict:
    return normalize_notebook_obj(parse_json_text(read_text_file(path), path.as_posix()), path.as_posix())


def strip_header_value(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def comment_content(line: str) -> str:
    stripped = line.rstrip("\r\n")
    if stripped.startswith("#"):
        stripped = stripped[1:]
        if stripped.startswith(" "):
            stripped = stripped[1:]
    return stripped


def parse_percent_header(lines: list[str]) -> tuple[dict, int]:
    if not lines or comment_content(lines[0]).strip() != "---":
        return {}, 0

    index = 1
    section: str | None = None
    data: dict[str, str] = {}
    while index < len(lines):
        content = comment_content(lines[index])
        if content.strip() == "---":
            return data, index + 1
        if content.strip():
            if not content.startswith(" "):
                if content.endswith(":"):
                    section = content[:-1].strip()
                else:
                    section = None
            else:
                key_line = content.strip()
                if ":" in key_line and section in {"minijupy", "kernelspec"}:
                    key, value = key_line.split(":", 1)
                    data[f"{section}.{key.strip()}"] = strip_header_value(value)
        index += 1
    fail("malformed percent header")


MARKER_RE = re.compile(r"^# %%\s*(.*?)\s*$")


def parse_marker(line: str) -> tuple[str, dict] | None:
    match = MARKER_RE.match(line.rstrip("\r\n"))
    if not match:
        return None
    payload = match.group(1).strip()
    cell_type = "code"
    metadata: dict = {}

    if payload.startswith("["):
        end = payload.find("]")
        if end < 0:
            fail("malformed percent marker")
        kind = payload[1:end].strip()
        if kind == "markdown" or kind == "md":
            cell_type = "markdown"
        elif kind == "raw":
            cell_type = "raw"
        else:
            fail(f"unsupported cell marker: {kind}")
        payload = payload[end + 1 :].strip()

    if payload:
        if not payload.startswith("{"):
            fail("malformed percent marker")
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            fail(f"malformed percent marker JSON: {exc.msg}")
        if not isinstance(parsed, dict):
            fail("malformed percent marker JSON")
        unknown = set(parsed) - {"id", "tags", "name"}
        if unknown:
            fail(f"unsupported marker metadata: {sorted(unknown)[0]}")
        if "id" in parsed:
            if not isinstance(parsed["id"], str):
                fail("invalid marker id")
            metadata["id"] = parsed["id"]
        if "tags" in parsed:
            if not isinstance(parsed["tags"], list) or not all(isinstance(tag, str) for tag in parsed["tags"]):
                fail("invalid marker tags")
            metadata["tags"] = list(parsed["tags"])
        if "name" in parsed:
            if not isinstance(parsed["name"], str):
                fail("invalid marker name")
            metadata["name"] = parsed["name"]

    return cell_type, metadata


def markdown_source_from_lines(lines: list[str]) -> str:
    converted = []
    for line in lines:
        if line.startswith("# "):
            converted.append(line[2:])
        else:
            converted.append(line)
    return "".join(converted)


def read_percent(path: Path) -> dict:
    text = read_text_file(path)
    lines = text.splitlines(keepends=True)
    header, body_start = parse_percent_header(lines)
    version = parse_header_version(header.get("minijupy.version"), path.as_posix())
    formats = header.get("minijupy.formats")
    kernelspec_name = header.get("kernelspec.name")

    raw_cells: list[dict] = []
    current: dict | None = None
    body: list[str] = []
    before_first: list[str] = []

    def finish(cell: dict, cell_body: list[str]) -> None:
        cell_type = cell["cell_type"]
        source = markdown_source_from_lines(cell_body) if cell_type == "markdown" else "".join(cell_body)
        metadata = {}
        if "tags" in cell:
            metadata["tags"] = cell["tags"]
        if "name" in cell:
            metadata["name"] = cell["name"]
        raw = {
            "cell_type": cell_type,
            "source": source,
            "metadata": metadata,
        }
        if "id" in cell:
            raw["id"] = cell["id"]
        raw_cells.append(raw)

    for line in lines[body_start:]:
        marker = parse_marker(line)
        if marker is not None:
            if current is None:
                if any(item.strip() for item in before_first):
                    finish({"cell_type": "code"}, before_first)
                before_first = []
            else:
                finish(current, body)
            cell_type, metadata = marker
            current = {"cell_type": cell_type, **metadata}
            body = []
        else:
            if current is None:
                before_first.append(line)
            else:
                body.append(line)

    if current is None:
        if any(item.strip() for item in before_first):
            finish({"cell_type": "code"}, before_first)
    else:
        finish(current, body)

    mini: dict = {}
    if formats is not None:
        mini["formats"] = formats
    mini["version"] = version
    metadata: dict = {"minijupy": mini}
    if kernelspec_name is not None:
        metadata["kernelspec"] = {"name": kernelspec_name}
    obj = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": metadata,
        "cells": raw_cells,
    }
    return normalize_notebook_obj(obj, path.as_posix())


def clone_model(model: dict) -> dict:
    return copy.deepcopy(model)


def set_model_formats(model: dict, formats: str = CANONICAL_FORMATS) -> dict:
    result = clone_model(model)
    result.setdefault("metadata", {}).setdefault("minijupy", {})["formats"] = formats
    return result


def model_version(model: dict) -> int:
    return parse_version(model.get("metadata", {}).get("minijupy", {}).get("version", 1), "model")


def model_formats(model: dict) -> str | None:
    value = model.get("metadata", {}).get("minijupy", {}).get("formats")
    return value if isinstance(value, str) else None


def serialize_ipynb(model: dict) -> str:
    return json.dumps(model, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def marker_json_for_cell(cell: dict) -> str:
    data: dict = {}
    if cell.get("id") is not None:
        data["id"] = cell["id"]
    metadata = cell.get("metadata", {})
    if isinstance(metadata, dict):
        if "tags" in metadata:
            data["tags"] = metadata["tags"]
        if "name" in metadata:
            data["name"] = metadata["name"]
    if not data:
        return ""
    return " " + json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def serialize_percent(model: dict) -> str:
    mini = model.get("metadata", {}).get("minijupy", {})
    kernelspec = model.get("metadata", {}).get("kernelspec", {})
    lines = ["# ---\n", "# minijupy:\n"]
    if isinstance(mini.get("formats"), str):
        lines.append(f"#   formats: {mini['formats']}\n")
    lines.append(f"#   version: {model_version(model)}\n")
    if isinstance(kernelspec, dict) and isinstance(kernelspec.get("name"), str):
        lines.extend(["# kernelspec:\n", f"#   name: {kernelspec['name']}\n"])
    lines.append("# ---\n")

    cells = model.get("cells", [])
    for index, cell in enumerate(cells):
        cell_type = cell["cell_type"]
        marker = "# %%"
        if cell_type == "markdown":
            marker += " [markdown]"
        elif cell_type == "raw":
            marker += " [raw]"
        marker += marker_json_for_cell(cell)
        lines.append(marker + "\n")

        source = cell.get("source", "")
        if cell_type == "markdown":
            body_lines = source.splitlines(keepends=True)
            if source and not body_lines:
                body_lines = [source]
            for body_line in body_lines:
                lines.append("# " + body_line)
        else:
            lines.append(source)
        if index < len(cells) - 1 and source and not source.endswith("\n"):
            lines.append("\n")
    return "".join(lines)


def text_model_from_ipynb_model(model: dict) -> dict:
    text_model = clone_model(model)
    for cell in text_model["cells"]:
        if cell["cell_type"] == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
    return text_model


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def merge_outputs_from_existing(new_model: dict, old_model: dict | None) -> dict:
    result = clone_model(new_model)
    for cell in result["cells"]:
        if cell["cell_type"] == "code":
            cell["execution_count"] = None
            cell["outputs"] = []

    if old_model is None:
        return result

    old_cells = old_model.get("cells", [])
    used: set[int] = set()

    def old_has_outputs(old_cell: dict) -> bool:
        return old_cell.get("cell_type") == "code" and (
            old_cell.get("execution_count") is not None or bool(old_cell.get("outputs", []))
        )

    def apply(new_cell: dict, old_cell: dict, old_index: int) -> None:
        used.add(old_index)
        new_cell["execution_count"] = copy.deepcopy(old_cell.get("execution_count", None))
        new_cell["outputs"] = copy.deepcopy(old_cell.get("outputs", []))

    for index, new_cell in enumerate(result["cells"]):
        if new_cell["cell_type"] != "code":
            continue
        chosen: int | None = None

        new_id = new_cell.get("id")
        for old_index, old_cell in enumerate(old_cells):
            if old_index not in used and old_has_outputs(old_cell) and old_cell.get("id") == new_id:
                chosen = old_index
                break

        if chosen is None:
            new_source_hash = source_hash(new_cell.get("source", ""))
            for old_index, old_cell in enumerate(old_cells):
                if old_index in used or not old_has_outputs(old_cell):
                    continue
                if old_cell.get("cell_type") == new_cell["cell_type"] and source_hash(old_cell.get("source", "")) == new_source_hash:
                    chosen = old_index
                    break

        if chosen is None and index < len(old_cells):
            old_cell = old_cells[index]
            if index not in used and old_has_outputs(old_cell) and old_cell.get("cell_type") == new_cell["cell_type"]:
                chosen = index

        if chosen is not None:
            apply(new_cell, old_cells[chosen], chosen)

    return result


def comparable_model(model: dict, include_outputs: bool = False) -> dict:
    mini = model.get("metadata", {}).get("minijupy", {})
    out = {
        "version": model_version(model),
        "formats": mini.get("formats") if isinstance(mini.get("formats"), str) else None,
        "kernelspec": model.get("metadata", {}).get("kernelspec", {}),
        "cells": [],
    }
    for cell in model.get("cells", []):
        entry = {
            "id": cell.get("id"),
            "cell_type": cell.get("cell_type"),
            "source": cell.get("source", ""),
            "tags": cell.get("metadata", {}).get("tags", []),
            "name": cell.get("metadata", {}).get("name"),
        }
        if include_outputs and cell.get("cell_type") == "code":
            entry["execution_count"] = cell.get("execution_count", None)
            entry["outputs"] = cell.get("outputs", [])
        out["cells"].append(entry)
    return out


def stable_hash(model: dict) -> str:
    payload = json.dumps(comparable_model(model, include_outputs=True), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compare_models(ipynb_model: dict | None, text_model: dict | None) -> list[str]:
    if ipynb_model is None or text_model is None:
        return []
    left = comparable_model(text_model_from_ipynb_model(ipynb_model), include_outputs=False)
    right = comparable_model(text_model, include_outputs=False)
    differences: list[str] = []

    for key, category in [("version", "version"), ("formats", "formats"), ("kernelspec", "kernelspec")]:
        if left.get(key) != right.get(key):
            differences.append(category)

    left_cells = left["cells"]
    right_cells = right["cells"]
    if len(left_cells) != len(right_cells):
        differences.append("cell_count")
    for l_cell, r_cell in zip(left_cells, right_cells):
        if l_cell["cell_type"] != r_cell["cell_type"]:
            differences.append("cell_type")
        if l_cell["source"] != r_cell["source"]:
            differences.append("source")
        if l_cell["id"] != r_cell["id"]:
            differences.append("id")
        if l_cell["tags"] != r_cell["tags"]:
            differences.append("tags")
        if l_cell["name"] != r_cell["name"]:
            differences.append("name")
    return sorted(set(differences), key=differences.index)


def state_path(config: Config) -> Path:
    return config.root / STATE_NAME


def load_state(config: Config) -> dict:
    path = state_path(config)
    if not path.exists():
        return {"pairs": {}}
    data = parse_json_text(read_text_file(path), path.as_posix())
    if not isinstance(data, dict) or not isinstance(data.get("pairs", {}), dict):
        fail("invalid state file")
    data.setdefault("pairs", {})
    return data


def state_versions(entry: dict | None) -> tuple[int | None, int | None]:
    if not isinstance(entry, dict):
        return None, None
    last = entry.get("last_synced", {})
    if not isinstance(last, dict):
        return None, None

    def clean(value):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    return clean(last.get("ipynb_version")), clean(last.get("text_version"))


def update_state_entry(state: dict, paths: PairPaths, ipynb_model: dict, text_model: dict) -> None:
    state.setdefault("pairs", {})[paths.ipynb_rel] = {
        "ipynb": paths.ipynb_rel,
        "text": paths.text_rel,
        "last_synced": {
            "ipynb_version": model_version(ipynb_model),
            "text_version": model_version(text_model),
            "ipynb_hash": stable_hash(ipynb_model),
            "text_hash": stable_hash(text_model),
        },
    }


def serialize_state(state: dict) -> str:
    ordered = {"pairs": {}}
    for key in sorted(state.get("pairs", {})):
        ordered["pairs"][key] = state["pairs"][key]
    return json.dumps(ordered, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def relative_to_base(path: PurePosixPath, base: PurePosixPath) -> PurePosixPath | None:
    try:
        return path.relative_to(base)
    except ValueError:
        return None


def pair_paths_for_input(input_path: str, config: Config) -> PairPaths:
    rel = normalized_rel(Path(input_path), config.root)
    rel_path = PurePosixPath(rel)
    suffix = rel_path.suffix
    if suffix not in {".ipynb", ".py"}:
        fail("unsupported file extension")

    if config.has_dirs:
        nb_base = PurePosixPath(config.notebook_dir)
        text_base = PurePosixPath(config.script_dir)
        if suffix == ".ipynb":
            sub = relative_to_base(rel_path, nb_base)
            if sub is None:
                fail("path mismatch: notebook outside notebook_dir")
            ipynb_rel = rel_path.as_posix()
            text_rel = (text_base / sub.with_suffix(".py")).as_posix()
        else:
            sub = relative_to_base(rel_path, text_base)
            if sub is None:
                fail("path mismatch: script outside script_dir")
            text_rel = rel_path.as_posix()
            ipynb_rel = (nb_base / sub.with_suffix(".ipynb")).as_posix()
    else:
        if suffix == ".ipynb":
            ipynb_rel = rel_path.as_posix()
            text_rel = rel_path.with_suffix(".py").as_posix()
        else:
            text_rel = rel_path.as_posix()
            ipynb_rel = rel_path.with_suffix(".ipynb").as_posix()

    return PairPaths(ipynb_rel, text_rel, abs_from_rel(config.root, ipynb_rel), abs_from_rel(config.root, text_rel))


def discover_pairs(config: Config) -> list[PairPaths]:
    if not config.path:
        fail("--all requires --config")

    search_roots: list[Path]
    if config.has_dirs:
        search_roots = [config.root / config.notebook_dir, config.root / config.script_dir]
    else:
        search_roots = [config.root]

    pairs: dict[str, PairPaths] = {}
    text_to_ipynb: dict[str, str] = {}
    for base in search_roots:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in {".ipynb", ".py"}:
                continue
            rel = normalized_rel(path, config.root)
            pair = pair_paths_for_input(rel, config)
            if pair.text_rel in text_to_ipynb and text_to_ipynb[pair.text_rel] != pair.ipynb_rel:
                fail("duplicate paired paths")
            text_to_ipynb[pair.text_rel] = pair.ipynb_rel
            pairs[pair.ipynb_rel] = pair
    return [pairs[key] for key in sorted(pairs)]


def read_existing_models(paths: PairPaths) -> tuple[dict | None, dict | None, list[str]]:
    errors: list[str] = []
    ipynb_model = None
    text_model = None
    if paths.ipynb_abs.exists():
        try:
            ipynb_model = read_ipynb(paths.ipynb_abs)
        except MiniJupyError as exc:
            errors.append(str(exc))
    if paths.text_abs.exists():
        try:
            text_model = read_percent(paths.text_abs)
        except MiniJupyError as exc:
            errors.append(str(exc))
    return ipynb_model, text_model, errors


def planned_writes_for_source(source: str, paths: PairPaths, config: Config) -> list[str]:
    if source == "ipynb":
        return [paths.text_rel, STATE_NAME]
    if source == "text":
        return [paths.ipynb_rel, STATE_NAME]
    return []


def evaluate_pair(paths: PairPaths, config: Config, state: dict, command: str, include_state_consistency: bool = False) -> dict:
    exists = {"ipynb": paths.ipynb_abs.exists(), "text": paths.text_abs.exists()}
    ipynb_model, text_model, errors = read_existing_models(paths)
    entry = state.get("pairs", {}).get(paths.ipynb_rel)
    last_ipynb, last_text = state_versions(entry)

    ipynb_version = model_version(ipynb_model) if ipynb_model is not None else None
    text_version = model_version(text_model) if text_model is not None else None
    missing = []
    if not exists["ipynb"]:
        missing.append(paths.ipynb_rel)
    if not exists["text"]:
        missing.append(paths.text_rel)
    if missing == [paths.ipynb_rel, paths.text_rel]:
        errors.append("both sides missing")

    differences = compare_models(ipynb_model, text_model)
    if include_state_consistency:
        if entry is None:
            differences.append("state")
        elif (
            (last_ipynb is not None and ipynb_version is not None and last_ipynb > ipynb_version)
            or (last_text is not None and text_version is not None and last_text > text_version)
        ):
            differences.append("state")
        elif entry.get("ipynb") not in {None, paths.ipynb_rel} or entry.get("text") not in {None, paths.text_rel}:
            differences.append("state")

    conflict = False
    source = "none"
    if errors:
        source = "none"
    elif not exists["ipynb"] and exists["text"]:
        source = "text"
    elif exists["ipynb"] and not exists["text"]:
        source = "ipynb"
    elif exists["ipynb"] and exists["text"]:
        if entry is None:
            source = "none"
            if command in {"status", "check"}:
                errors.append("missing state entry")
        else:
            changed_ipynb = last_ipynb is not None and ipynb_version is not None and ipynb_version > last_ipynb
            changed_text = last_text is not None and text_version is not None and text_version > last_text
            if changed_ipynb and changed_text:
                conflict = True
                source = "none"
            elif changed_ipynb:
                source = "ipynb"
            elif changed_text:
                source = "text"

    planned = [] if errors or conflict else planned_writes_for_source(source, paths, config)
    roundtrip_ok = not errors and not conflict and exists["ipynb"] and exists["text"] and not differences

    return {
        "ipynb": paths.ipynb_rel,
        "text": paths.text_rel,
        "exists": exists,
        "versions": {
            "ipynb": ipynb_version,
            "text": text_version,
            "last_ipynb": last_ipynb,
            "last_text": last_text,
        },
        "source": source,
        "conflict": conflict,
        "missing": missing,
        "planned_writes": planned,
        "roundtrip_ok": roundtrip_ok,
        "differences": sorted(set(differences), key=differences.index),
        "errors": errors,
    }


def summary_for_pairs(pairs: list[dict]) -> dict:
    return {
        "pairs": len(pairs),
        "conflicts": sum(1 for pair in pairs if pair.get("conflict")),
        "missing": sum(len(pair.get("missing", [])) for pair in pairs),
        "planned_writes": sum(len(pair.get("planned_writes", [])) for pair in pairs),
        "errors": sum(len(pair.get("errors", [])) for pair in pairs),
    }


def response_for_pairs(command: str, config: Config, pairs: list[dict]) -> dict:
    return {
        "ok": True,
        "command": command,
        "root": display_root(config.root),
        "pairs": pairs,
        "summary": summary_for_pairs(pairs),
    }


def write_all_atomic(writes: dict[Path, str]) -> None:
    temp_paths: list[tuple[Path, Path]] = []
    try:
        for path, content in writes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
            temp_paths.append((path, tmp_path))
        for path, tmp_path in temp_paths:
            os.replace(tmp_path, path)
    except Exception as exc:
        for _, tmp_path in temp_paths:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
        if isinstance(exc, MiniJupyError):
            raise
        fail(f"write failed: {exc}")


def rel_for_output(path_arg: str, root: Path) -> str:
    path = Path(path_arg)
    if path.is_absolute():
        try:
            return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
        except ValueError:
            return path.resolve(strict=False).as_posix()
    return path.as_posix()


def output_path(path_arg: str) -> Path:
    path = Path(path_arg)
    return path if path.is_absolute() else Path.cwd() / path


def command_inspect(args) -> dict:
    config = parse_config(args.config)
    path = Path(args.input)
    full = path if path.is_absolute() else Path.cwd() / path
    suffix = full.suffix
    if suffix == ".ipynb":
        fmt = "ipynb"
        model = read_ipynb(full)
    elif suffix == ".py":
        fmt = "py:percent"
        model = read_percent(full)
    else:
        fail("unsupported file extension")
    return {
        "ok": True,
        "command": "inspect",
        "path": rel_for_output(args.input, config.root),
        "format": fmt,
        "version": model_version(model),
        "notebook": model,
    }


def command_paths(args) -> dict:
    config = parse_config(args.config)
    paths = pair_paths_for_input(args.input, config)
    return {
        "ok": True,
        "command": "paths",
        "root": display_root(config.root),
        "input": normalized_rel(Path(args.input), config.root),
        "ipynb": paths.ipynb_rel,
        "text": paths.text_rel,
        "exists": {"ipynb": paths.ipynb_abs.exists(), "text": paths.text_abs.exists()},
    }


def command_to_text(args) -> dict:
    config = parse_config(args.config)
    input_path = output_path(args.input)
    output = output_path(args.output)
    if input_path.suffix != ".ipynb":
        fail("to-text input must be .ipynb")
    if output.suffix != ".py":
        fail("to-text output must be .py")
    model = read_ipynb(input_path)
    write_all_atomic({output: serialize_percent(text_model_from_ipynb_model(model))})
    return {
        "ok": True,
        "command": "to-text",
        "input": rel_for_output(args.input, config.root),
        "output": rel_for_output(args.output, config.root),
    }


def command_to_ipynb(args) -> dict:
    config = parse_config(args.config)
    input_path = output_path(args.input)
    output = output_path(args.output)
    if input_path.suffix != ".py":
        fail("to-ipynb input must be .py")
    if output.suffix != ".ipynb":
        fail("to-ipynb output must be .ipynb")
    model = read_percent(input_path)
    old = read_ipynb(output) if args.update and output.exists() else None
    final_model = merge_outputs_from_existing(model, old)
    write_all_atomic({output: serialize_ipynb(final_model)})
    return {
        "ok": True,
        "command": "to-ipynb",
        "input": rel_for_output(args.input, config.root),
        "output": rel_for_output(args.output, config.root),
        "updated": bool(args.update),
    }


def plan_pair(paths: PairPaths, config: Config, state: dict, input_arg: str) -> tuple[dict, dict[Path, str], dict]:
    input_rel = normalized_rel(Path(input_arg), config.root)
    input_side = "ipynb" if PurePosixPath(input_rel).suffix == ".ipynb" else "text"
    exists = {"ipynb": paths.ipynb_abs.exists(), "text": paths.text_abs.exists()}
    if not exists["ipynb"] and not exists["text"]:
        fail("both sides missing")
    source = input_side if exists[input_side] else ("ipynb" if exists["ipynb"] else "text")

    if source == "ipynb":
        source_model = read_ipynb(paths.ipynb_abs)
        if paths.text_abs.exists():
            read_percent(paths.text_abs)
        final_ipynb = set_model_formats(source_model)
        final_text = text_model_from_ipynb_model(final_ipynb)
    else:
        source_model = read_percent(paths.text_abs)
        final_text = set_model_formats(source_model)
        old_ipynb = read_ipynb(paths.ipynb_abs) if paths.ipynb_abs.exists() else None
        final_ipynb = merge_outputs_from_existing(final_text, old_ipynb)

    new_state = copy.deepcopy(state)
    update_state_entry(new_state, paths, final_ipynb, final_text)
    writes = {
        paths.ipynb_abs: serialize_ipynb(final_ipynb),
        paths.text_abs: serialize_percent(final_text),
        state_path(config): serialize_state(new_state),
    }
    pair = evaluate_pair(paths, config, new_state, "pair")
    pair["source"] = source
    pair["conflict"] = False
    pair["planned_writes"] = [paths.ipynb_rel, paths.text_rel, STATE_NAME]
    pair["versions"] = {
        "ipynb": model_version(final_ipynb),
        "text": model_version(final_text),
        "last_ipynb": model_version(final_ipynb),
        "last_text": model_version(final_text),
    }
    pair["missing"] = []
    pair["exists"] = {"ipynb": True, "text": True}
    pair["differences"] = compare_models(final_ipynb, final_text)
    pair["roundtrip_ok"] = not pair["differences"]
    pair["errors"] = []
    return pair, writes, new_state


def command_pair(args) -> dict:
    config = parse_config(args.config)
    state = load_state(config)
    paths = pair_paths_for_input(args.input, config)
    pair, writes, _ = plan_pair(paths, config, state, args.input)
    write_all_atomic(writes)
    return {
        "ok": True,
        "command": "pair",
        "root": display_root(config.root),
        "pair": pair,
    }


def command_status_or_check(args, command: str) -> dict:
    config = parse_config(args.config)
    if args.all and not args.config:
        fail("--all requires --config")
    if bool(args.all) == bool(args.input):
        fail(f"{command} requires exactly one of --input or --all")
    state = load_state(config)
    include_state = command == "check"
    if args.all:
        pairs = [evaluate_pair(paths, config, state, command, include_state) for paths in discover_pairs(config)]
    else:
        paths = pair_paths_for_input(args.input, config)
        pairs = [evaluate_pair(paths, config, state, command, include_state)]
    return response_for_pairs(command, config, pairs)


def plan_sync_pair(paths: PairPaths, config: Config, state: dict, explicit_source: str | None) -> tuple[dict, dict[Path, str], dict]:
    base_pair = evaluate_pair(paths, config, state, "sync", include_state_consistency=False)
    entry = state.get("pairs", {}).get(paths.ipynb_rel)
    exists = base_pair["exists"]
    if base_pair["errors"]:
        fail("; ".join(base_pair["errors"]))
    if not exists["ipynb"] and not exists["text"]:
        fail("both sides missing")

    source = explicit_source or base_pair["source"]
    conflict = base_pair["conflict"]
    if explicit_source:
        if not exists[explicit_source]:
            fail(f"selected source missing: {explicit_source}")
        conflict = False
    else:
        if conflict:
            fail("conflict without explicit --source")
        if exists["ipynb"] and exists["text"] and entry is None:
            fail("missing state entry")

    if source == "none":
        base_pair["planned_writes"] = []
        return base_pair, {}, copy.deepcopy(state)

    new_state = copy.deepcopy(state)
    writes: dict[Path, str] = {}
    if source == "ipynb":
        ipynb_model = read_ipynb(paths.ipynb_abs)
        text_model = text_model_from_ipynb_model(ipynb_model)
        writes[paths.text_abs] = serialize_percent(text_model)
        update_state_entry(new_state, paths, ipynb_model, text_model)
    elif source == "text":
        text_model = read_percent(paths.text_abs)
        old_ipynb = read_ipynb(paths.ipynb_abs) if paths.ipynb_abs.exists() else None
        ipynb_model = merge_outputs_from_existing(text_model, old_ipynb)
        writes[paths.ipynb_abs] = serialize_ipynb(ipynb_model)
        update_state_entry(new_state, paths, ipynb_model, text_model)
    else:
        fail("invalid sync source")

    writes[state_path(config)] = serialize_state(new_state)
    pair = evaluate_pair(paths, config, new_state, "sync", include_state_consistency=False)
    pair["source"] = source
    pair["conflict"] = conflict
    pair["planned_writes"] = planned_writes_for_source(source, paths, config)
    pair["errors"] = []
    if source == "ipynb":
        pair["versions"]["text"] = pair["versions"]["ipynb"]
        pair["versions"]["last_ipynb"] = pair["versions"]["ipynb"]
        pair["versions"]["last_text"] = pair["versions"]["ipynb"]
    elif source == "text":
        pair["versions"]["ipynb"] = pair["versions"]["text"]
        pair["versions"]["last_ipynb"] = pair["versions"]["text"]
        pair["versions"]["last_text"] = pair["versions"]["text"]
    pair["missing"] = []
    pair["exists"] = {"ipynb": True, "text": True}
    pair["differences"] = []
    pair["roundtrip_ok"] = True
    return pair, writes, new_state


def command_sync(args) -> dict:
    config = parse_config(args.config)
    if args.all and not args.config:
        fail("--all requires --config")
    if bool(args.all) == bool(args.input):
        fail("sync requires exactly one of --input or --all")
    state = load_state(config)

    if args.all:
        pairs_paths = discover_pairs(config)
        planned_pairs: list[dict] = []
        all_writes: dict[Path, str] = {}
        new_state = copy.deepcopy(state)
        for paths in pairs_paths:
            pair, writes, new_state = plan_sync_pair(paths, config, new_state, args.source)
            planned_pairs.append(pair)
            for path, content in writes.items():
                if path in all_writes and all_writes[path] != content and path != state_path(config):
                    fail("duplicate paired paths")
                all_writes[path] = content
        if state_path(config) in all_writes:
            all_writes[state_path(config)] = serialize_state(new_state)
        write_all_atomic(all_writes)
        return response_for_pairs("sync", config, planned_pairs)

    paths = pair_paths_for_input(args.input, config)
    pair, writes, _ = plan_sync_pair(paths, config, state, args.source)
    write_all_atomic(writes)
    return response_for_pairs("sync", config, [pair])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minijupy.py")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_p = sub.add_parser("inspect")
    inspect_p.add_argument("--input", required=True)
    inspect_p.add_argument("--config")

    paths_p = sub.add_parser("paths")
    paths_p.add_argument("--input", required=True)
    paths_p.add_argument("--config")

    to_text = sub.add_parser("to-text")
    to_text.add_argument("--input", required=True)
    to_text.add_argument("--output", required=True)
    to_text.add_argument("--config")

    to_ipynb = sub.add_parser("to-ipynb")
    to_ipynb.add_argument("--input", required=True)
    to_ipynb.add_argument("--output", required=True)
    to_ipynb.add_argument("--config")
    to_ipynb.add_argument("--update", action="store_true")

    pair_p = sub.add_parser("pair")
    pair_p.add_argument("--input", required=True)
    pair_p.add_argument("--config")

    for name in ("status", "check"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--input")
        cmd.add_argument("--all", action="store_true")
        cmd.add_argument("--config")

    sync = sub.add_parser("sync")
    sync.add_argument("--input")
    sync.add_argument("--all", action="store_true")
    sync.add_argument("--config")
    sync.add_argument("--source", choices=["ipynb", "text"])

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
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
            result = command_status_or_check(args, "status")
        elif args.command == "check":
            result = command_status_or_check(args, "check")
        elif args.command == "sync":
            result = command_sync(args)
        else:
            fail("unsupported command")
    except MiniJupyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

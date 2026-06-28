#!/usr/bin/env python3
"""MiniJupy: a small deterministic paired notebook CLI."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


FORMATS = "ipynb,py:percent"
STATE_NAME = ".minijupy-state.json"


class MiniJupyError(Exception):
    pass


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def posix_path(path: str | os.PathLike[str]) -> str:
    return Path(path).as_posix()


def rel_to_root(path: str | os.PathLike[str], root: Path) -> str:
    return os.path.relpath(Path(path).resolve(), root.resolve()).replace(os.sep, "/")


def rel_display(path: Path, root: Path) -> str:
    try:
        return rel_to_root(path, root)
    except ValueError:
        return posix_path(path)


def clean_rel(path: str) -> str:
    cleaned = PurePosixPath(path.replace("\\", "/")).as_posix()
    return "." if cleaned == "" else cleaned


def root_label(root: Path) -> str:
    rel = os.path.relpath(root.resolve(), Path.cwd().resolve()).replace(os.sep, "/")
    return "." if rel == "." else rel


def split_lines_keep(source: str) -> list[str]:
    return source.splitlines(True)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MiniJupyError(f"cannot read {path}: {exc}") from exc


def read_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed JSON notebook: {path}: {exc}") from exc


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = -1
    tmp_name: str | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            handle.write(text)
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if fd != -1:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def print_json(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))


def validate_version(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MiniJupyError(f"invalid version in {context}")
    return value


def parse_scalar(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


class Config:
    def __init__(self, config_path: Path | None):
        self.config_path = config_path.resolve() if config_path else None
        self.root = self.config_path.parent if self.config_path else Path.cwd().resolve()
        self.formats = FORMATS
        self.notebook_dir: str | None = None
        self.script_dir: str | None = None
        if self.config_path:
            self._load()

    @property
    def state_path(self) -> Path:
        return self.root / STATE_NAME

    def _load(self) -> None:
        if not self.config_path or not self.config_path.exists():
            raise MiniJupyError("invalid config: config file does not exist")
        values: dict[str, str] = {}
        for line_no, raw in enumerate(read_text(self.config_path).splitlines(), start=1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", stripped)
            if not match:
                raise MiniJupyError(f"invalid config at line {line_no}")
            key, value = match.group(1), parse_scalar(match.group(2))
            if key not in {"formats", "notebook_dir", "script_dir"}:
                raise MiniJupyError(f"invalid config key: {key}")
            values[key] = value
        if "formats" in values:
            if values["formats"] not in {FORMATS, "py:percent,ipynb"}:
                raise MiniJupyError("invalid config: unsupported formats")
            self.formats = values["formats"]
        self.notebook_dir = values.get("notebook_dir")
        self.script_dir = values.get("script_dir")
        if (self.notebook_dir is None) != (self.script_dir is None):
            raise MiniJupyError("invalid config: notebook_dir and script_dir must both be set")
        for key in ("notebook_dir", "script_dir"):
            value = values.get(key)
            if value is not None and Path(value).is_absolute():
                raise MiniJupyError(f"invalid config: {key} must be relative")
            if value is not None and clean_rel(value).startswith(".."):
                raise MiniJupyError(f"invalid config: {key} must stay under root")


def is_under(rel: str, directory: str) -> tuple[bool, str]:
    directory = clean_rel(directory).rstrip("/")
    rel = clean_rel(rel)
    if rel == directory:
        return True, ""
    prefix = directory + "/"
    if rel.startswith(prefix):
        return True, rel[len(prefix) :]
    return False, ""


def pair_paths(input_path: Path, config: Config) -> dict[str, Any]:
    rel = rel_to_root(input_path, config.root)
    suffix = Path(rel).suffix
    if suffix not in {".ipynb", ".py"}:
        raise MiniJupyError("unsupported file extension")

    if config.notebook_dir is not None and config.script_dir is not None:
        if suffix == ".ipynb":
            ok, sub = is_under(rel, config.notebook_dir)
            if not ok:
                raise MiniJupyError("path mismatch: notebook is outside notebook_dir")
            stem = str(PurePosixPath(sub).with_suffix(".py"))
            text_rel = clean_rel(str(PurePosixPath(config.script_dir) / stem))
            ipynb_rel = clean_rel(rel)
        else:
            ok, sub = is_under(rel, config.script_dir)
            if not ok:
                raise MiniJupyError("path mismatch: script is outside script_dir")
            stem = str(PurePosixPath(sub).with_suffix(".ipynb"))
            ipynb_rel = clean_rel(str(PurePosixPath(config.notebook_dir) / stem))
            text_rel = clean_rel(rel)
    else:
        rel_path = PurePosixPath(rel)
        if suffix == ".ipynb":
            ipynb_rel = clean_rel(rel)
            text_rel = clean_rel(str(rel_path.with_suffix(".py")))
        else:
            text_rel = clean_rel(rel)
            ipynb_rel = clean_rel(str(rel_path.with_suffix(".ipynb")))
    if ipynb_rel == text_rel:
        raise MiniJupyError("duplicate paired paths")
    return {
        "input": clean_rel(rel),
        "ipynb": ipynb_rel,
        "text": text_rel,
        "ipynb_path": config.root / ipynb_rel,
        "text_path": config.root / text_rel,
        "key": ipynb_rel,
    }


def parse_cell_metadata(raw: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if not isinstance(raw, dict):
        return metadata
    if "tags" in raw:
        tags = raw["tags"]
        if not isinstance(tags, list) or not all(isinstance(item, str) for item in tags):
            raise MiniJupyError("invalid cell tags")
        metadata["tags"] = list(tags)
    if "name" in raw:
        if not isinstance(raw["name"], str):
            raise MiniJupyError("invalid cell name")
        metadata["name"] = raw["name"]
    return metadata


def normalize_source(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "".join(value)
    raise MiniJupyError("invalid cell source")


def normalize_notebook(raw: Any, context: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise MiniJupyError("malformed notebook")
    if raw.get("nbformat") != 4:
        raise MiniJupyError("unsupported notebook nbformat")

    top_meta = raw.get("metadata", {})
    if top_meta is None:
        top_meta = {}
    if not isinstance(top_meta, dict):
        raise MiniJupyError("invalid notebook metadata")
    mini = top_meta.get("minijupy", {})
    if mini is None:
        mini = {}
    if not isinstance(mini, dict):
        raise MiniJupyError("invalid minijupy metadata")
    version = validate_version(mini.get("version", 1), context)
    metadata: dict[str, Any] = {
        "kernelspec": copy.deepcopy(top_meta.get("kernelspec", {}))
        if isinstance(top_meta.get("kernelspec", {}), dict)
        else {},
        "language_info": copy.deepcopy(top_meta.get("language_info", {}))
        if isinstance(top_meta.get("language_info", {}), dict)
        else {},
        "minijupy": {"version": version},
    }
    if "formats" in mini:
        if not isinstance(mini["formats"], str):
            raise MiniJupyError("invalid minijupy formats")
        metadata["minijupy"]["formats"] = mini["formats"]

    cells_raw = raw.get("cells", [])
    if not isinstance(cells_raw, list):
        raise MiniJupyError("invalid notebook cells")
    ids: set[str] = set()
    cells: list[dict[str, Any]] = []
    for index, raw_cell in enumerate(cells_raw, start=1):
        if not isinstance(raw_cell, dict):
            raise MiniJupyError("invalid cell")
        cell_type = raw_cell.get("cell_type")
        if cell_type not in {"code", "markdown", "raw"}:
            raise MiniJupyError("unsupported cell type")
        cell_id = raw_cell.get("id", f"c{index}")
        if not isinstance(cell_id, str) or not cell_id:
            raise MiniJupyError("invalid cell id")
        if cell_id in ids:
            raise MiniJupyError("duplicate cell ids")
        ids.add(cell_id)
        cell: dict[str, Any] = {
            "id": cell_id,
            "cell_type": cell_type,
            "source": normalize_source(raw_cell.get("source", "")),
            "metadata": parse_cell_metadata(raw_cell.get("metadata", {})),
        }
        if cell_type == "code":
            cell["execution_count"] = raw_cell.get("execution_count", None)
            outputs = raw_cell.get("outputs", [])
            cell["outputs"] = copy.deepcopy(outputs) if isinstance(outputs, list) else []
        cells.append(cell)

    return {
        "nbformat": 4,
        "nbformat_minor": raw.get("nbformat_minor", 5),
        "metadata": metadata,
        "cells": cells,
    }


def parse_header_value(line: str) -> tuple[int, str, str] | None:
    without_hash = line[1:] if line.startswith("#") else line
    if without_hash.startswith(" "):
        without_hash = without_hash[1:]
    if not without_hash.strip():
        return None
    indent = len(without_hash) - len(without_hash.lstrip(" "))
    text = without_hash.strip()
    if ":" not in text:
        return None
    key, value = text.split(":", 1)
    return indent, key.strip(), parse_scalar(value.strip())


def parse_percent_header(lines: list[str]) -> tuple[dict[str, Any], int]:
    metadata: dict[str, Any] = {"minijupy": {"version": 1}}
    if not lines or lines[0].strip() != "# ---":
        return metadata, 0
    section: str | None = None
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "# ---":
            end = index + 1
            break
        parsed = parse_header_value(lines[index])
        if parsed is None:
            continue
        indent, key, value = parsed
        if indent == 0 and value == "":
            section = key
            continue
        if indent == 0:
            section = None
        if section == "minijupy" and key == "formats":
            metadata["minijupy"]["formats"] = value
        elif section == "minijupy" and key == "version":
            try:
                metadata["minijupy"]["version"] = int(value)
            except ValueError as exc:
                raise MiniJupyError("invalid version in percent header") from exc
        elif section == "kernelspec" and key == "name":
            metadata.setdefault("kernelspec", {})["name"] = value
    if end is None:
        raise MiniJupyError("invalid percent header")
    validate_version(metadata["minijupy"].get("version", 1), "percent header")
    return metadata, end


MARKER_RE = re.compile(r"^# %%\s*(.*)$")
BRACKET_RE = re.compile(r"^\[(markdown|md|raw)\]\s*(.*)$")


def parse_marker(rest: str) -> tuple[str, dict[str, Any]]:
    rest = rest.strip()
    cell_type = "code"
    if rest.startswith("["):
        match = BRACKET_RE.match(rest)
        if not match:
            raise MiniJupyError("unsupported percent cell marker")
        cell_type = "markdown" if match.group(1) in {"markdown", "md"} else "raw"
        rest = match.group(2).strip()
    marker_meta: dict[str, Any] = {}
    if rest:
        if not rest.startswith("{"):
            raise MiniJupyError("unsupported percent cell marker")
        try:
            marker_meta = json.loads(rest)
        except json.JSONDecodeError as exc:
            raise MiniJupyError("malformed percent marker JSON") from exc
        if not isinstance(marker_meta, dict):
            raise MiniJupyError("malformed percent marker JSON")
        unknown = set(marker_meta) - {"id", "tags", "name"}
        if unknown:
            raise MiniJupyError("unsupported percent marker metadata")
        if "id" in marker_meta and not isinstance(marker_meta["id"], str):
            raise MiniJupyError("invalid cell id")
        marker_meta = parse_cell_metadata(marker_meta) | (
            {"id": marker_meta["id"]} if "id" in marker_meta else {}
        )
    return cell_type, marker_meta


def parse_percent_script(text: str, context: str) -> dict[str, Any]:
    lines = split_lines_keep(text)
    header_meta, start = parse_percent_header(lines)
    cells: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    body: list[str] = []
    seen_marker = False

    def finish_current() -> None:
        nonlocal current, body
        if current is None:
            return
        source = "".join(body)
        if current["cell_type"] == "markdown":
            source = "".join(line[2:] if line.startswith("# ") else line for line in body)
        current["source"] = source
        cells.append(current)
        current = None
        body = []

    for line in lines[start:]:
        match = MARKER_RE.match(line)
        if match:
            finish_current()
            seen_marker = True
            cell_type, marker_meta = parse_marker(match.group(1))
            current = {
                "cell_type": cell_type,
                "metadata": {
                    key: value for key, value in marker_meta.items() if key in {"tags", "name"}
                },
            }
            if "id" in marker_meta:
                current["id"] = marker_meta["id"]
            if cell_type == "code":
                current["execution_count"] = None
                current["outputs"] = []
            continue
        if current is None:
            if not seen_marker and line.strip():
                current = {
                    "cell_type": "code",
                    "metadata": {},
                    "execution_count": None,
                    "outputs": [],
                }
                body.append(line)
            elif seen_marker:
                body.append(line)
            continue
        body.append(line)
    finish_current()

    ids: set[str] = set()
    normalized_cells: list[dict[str, Any]] = []
    for index, cell in enumerate(cells, start=1):
        cell_id = cell.get("id", f"c{index}")
        if cell_id in ids:
            raise MiniJupyError("duplicate cell ids")
        ids.add(cell_id)
        out = {
            "id": cell_id,
            "cell_type": cell["cell_type"],
            "source": cell.get("source", ""),
            "metadata": cell.get("metadata", {}),
        }
        if cell["cell_type"] == "code":
            out["execution_count"] = None
            out["outputs"] = []
        normalized_cells.append(out)

    metadata = {
        "kernelspec": header_meta.get("kernelspec", {}),
        "language_info": {},
        "minijupy": {"version": validate_version(header_meta["minijupy"].get("version", 1), context)},
    }
    if "formats" in header_meta.get("minijupy", {}):
        metadata["minijupy"]["formats"] = header_meta["minijupy"]["formats"]
    return {"nbformat": 4, "nbformat_minor": 5, "metadata": metadata, "cells": normalized_cells}


def read_model(path: Path) -> dict[str, Any]:
    suffix = path.suffix
    if suffix == ".ipynb":
        return normalize_notebook(read_json(path), str(path))
    if suffix == ".py":
        return parse_percent_script(read_text(path), str(path))
    raise MiniJupyError("unsupported file extension")


def model_version(model: dict[str, Any]) -> int:
    return model["metadata"]["minijupy"]["version"]


def model_formats(model: dict[str, Any]) -> str | None:
    return model["metadata"]["minijupy"].get("formats")


def set_formats(model: dict[str, Any], formats: str = FORMATS) -> dict[str, Any]:
    updated = copy.deepcopy(model)
    updated.setdefault("metadata", {}).setdefault("minijupy", {})["formats"] = formats
    return updated


def text_representable_model(model: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(model)
    for cell in updated.get("cells", []):
        if cell.get("cell_type") == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
    return updated


def marker_metadata(cell: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if "id" in cell:
        metadata["id"] = cell["id"]
    cell_meta = cell.get("metadata", {})
    if "tags" in cell_meta:
        metadata["tags"] = cell_meta["tags"]
    if "name" in cell_meta:
        metadata["name"] = cell_meta["name"]
    return metadata


def write_percent_model(model: dict[str, Any]) -> str:
    mini = model["metadata"]["minijupy"]
    lines: list[str] = [
        "# ---\n",
        "# minijupy:\n",
    ]
    if "formats" in mini:
        lines.append(f"#   formats: {mini['formats']}\n")
    lines.append(f"#   version: {mini['version']}\n")
    kernelspec = model["metadata"].get("kernelspec", {})
    if isinstance(kernelspec, dict) and kernelspec.get("name"):
        lines.extend(["# kernelspec:\n", f"#   name: {kernelspec['name']}\n"])
    lines.append("# ---\n")
    for cell in model["cells"]:
        cell_type = cell["cell_type"]
        marker = "# %%"
        if cell_type == "markdown":
            marker += " [markdown]"
        elif cell_type == "raw":
            marker += " [raw]"
        metadata = marker_metadata(cell)
        if metadata:
            marker += " " + json.dumps(
                metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        lines.append(marker + "\n")
        source = cell.get("source", "")
        if cell_type == "markdown":
            lines.extend("# " + part for part in split_lines_keep(source))
            if source and not source.endswith(("\n", "\r")):
                pass
        else:
            lines.append(source)
            if source and not source.endswith(("\n", "\r")):
                pass
    return "".join(lines)


def write_ipynb_model(model: dict[str, Any]) -> str:
    clean = copy.deepcopy(model)
    clean["nbformat"] = 4
    clean["nbformat_minor"] = clean.get("nbformat_minor", 5)
    return json.dumps(clean, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def source_hash(cell: dict[str, Any]) -> str:
    payload = {"cell_type": cell["cell_type"], "source": cell.get("source", "")}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def preserve_outputs(new_model: dict[str, Any], old_ipynb: dict[str, Any] | None) -> dict[str, Any]:
    if old_ipynb is None:
        return new_model
    updated = copy.deepcopy(new_model)
    old_cells = old_ipynb.get("cells", [])
    used: set[int] = set()
    id_index: dict[str, int] = {}
    for index, cell in enumerate(old_cells):
        if cell.get("id"):
            id_index[cell["id"]] = index

    for pos, cell in enumerate(updated["cells"]):
        if cell["cell_type"] != "code":
            continue
        match_index: int | None = None
        cell_id = cell.get("id")
        if cell_id in id_index and id_index[cell_id] not in used:
            match_index = id_index[cell_id]
        if match_index is None:
            wanted_hash = source_hash(cell)
            for idx, old in enumerate(old_cells):
                if idx in used or old.get("cell_type") != cell["cell_type"]:
                    continue
                if source_hash(old) == wanted_hash:
                    match_index = idx
                    break
        if match_index is None and pos < len(old_cells) and pos not in used:
            old = old_cells[pos]
            if old.get("cell_type") == cell["cell_type"]:
                match_index = pos
        if match_index is not None:
            used.add(match_index)
            old = old_cells[match_index]
            cell["execution_count"] = old.get("execution_count", None)
            cell["outputs"] = copy.deepcopy(old.get("outputs", []))
        else:
            cell["execution_count"] = None
            cell["outputs"] = []
    return updated


def stable_hash(model: dict[str, Any]) -> str:
    payload = json.dumps(model, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_state(config: Config) -> dict[str, Any]:
    if not config.state_path.exists():
        return {"pairs": {}}
    try:
        state = json.loads(read_text(config.state_path))
    except json.JSONDecodeError as exc:
        raise MiniJupyError("malformed state file") from exc
    if not isinstance(state, dict):
        raise MiniJupyError("malformed state file")
    pairs = state.get("pairs", {})
    if not isinstance(pairs, dict):
        raise MiniJupyError("malformed state file")
    return {"pairs": pairs}


def state_entry(ipynb_rel: str, text_rel: str, ipynb: dict[str, Any], text: dict[str, Any]) -> dict[str, Any]:
    return {
        "ipynb": ipynb_rel,
        "text": text_rel,
        "last_synced": {
            "ipynb_version": model_version(ipynb),
            "text_version": model_version(text),
            "ipynb_hash": stable_hash(ipynb),
            "text_hash": stable_hash(text),
        },
    }


def write_state(config: Config, state: dict[str, Any]) -> None:
    atomic_write_text(
        config.state_path,
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def comparable_model(model: dict[str, Any]) -> dict[str, Any]:
    mini = model["metadata"]["minijupy"]
    return {
        "version": mini.get("version"),
        "formats": mini.get("formats"),
        "kernelspec": model["metadata"].get("kernelspec", {}),
        "cells": [
            {
                "id": cell.get("id"),
                "cell_type": cell.get("cell_type"),
                "source": cell.get("source", ""),
                "metadata": cell.get("metadata", {}),
            }
            for cell in model.get("cells", [])
        ],
    }


def compare_models(ipynb: dict[str, Any], text: dict[str, Any]) -> list[str]:
    diffs: set[str] = set()
    a, b = comparable_model(ipynb), comparable_model(text)
    if a["version"] != b["version"]:
        diffs.add("version")
    if a["formats"] != b["formats"]:
        diffs.add("formats")
    a_cells, b_cells = a["cells"], b["cells"]
    if len(a_cells) != len(b_cells):
        diffs.add("cell_count")
    for ac, bc in zip(a_cells, b_cells):
        if ac["cell_type"] != bc["cell_type"]:
            diffs.add("cell_type")
        if ac["source"] != bc["source"]:
            diffs.add("source")
        if ac["id"] != bc["id"]:
            diffs.add("id")
        if ac["metadata"].get("tags") != bc["metadata"].get("tags"):
            diffs.add("tags")
        if ac["metadata"].get("name") != bc["metadata"].get("name"):
            diffs.add("name")
    return sorted(diffs)


def output_differences_after_preservation(ipynb: dict[str, Any], text: dict[str, Any]) -> bool:
    preserved = preserve_outputs(copy.deepcopy(text), ipynb)
    old_cells = [cell for cell in ipynb.get("cells", []) if cell.get("cell_type") == "code"]
    new_cells = [cell for cell in preserved.get("cells", []) if cell.get("cell_type") == "code"]
    for old, new in zip(old_cells, new_cells):
        if old.get("id") != new.get("id"):
            continue
        if old.get("source", "") != new.get("source", ""):
            continue
        if old.get("execution_count", None) != new.get("execution_count", None):
            return True
        if old.get("outputs", []) != new.get("outputs", []):
            return True
    return False


def summarize(pairs: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "pairs": len(pairs),
        "conflicts": sum(1 for pair in pairs if pair.get("conflict")),
        "missing": sum(len(pair.get("missing", [])) for pair in pairs),
        "planned_writes": sum(len(pair.get("planned_writes", [])) for pair in pairs),
        "errors": sum(len(pair.get("errors", [])) for pair in pairs),
    }


def pair_status(paths: dict[str, Any], config: Config, state: dict[str, Any], check: bool = False) -> dict[str, Any]:
    ipynb_path: Path = paths["ipynb_path"]
    text_path: Path = paths["text_path"]
    exists = {"ipynb": ipynb_path.exists(), "text": text_path.exists()}
    missing = [name for name, present in exists.items() if not present]
    errors: list[str] = []
    ipynb_model: dict[str, Any] | None = None
    text_model: dict[str, Any] | None = None
    ipynb_version: int | None = None
    text_version: int | None = None

    if exists["ipynb"]:
        try:
            ipynb_model = read_model(ipynb_path)
            ipynb_version = model_version(ipynb_model)
        except MiniJupyError as exc:
            errors.append(str(exc))
    if exists["text"]:
        try:
            text_model = read_model(text_path)
            text_version = model_version(text_model)
        except MiniJupyError as exc:
            errors.append(str(exc))

    entry = state.get("pairs", {}).get(paths["key"])
    last = entry.get("last_synced", {}) if isinstance(entry, dict) else {}
    last_i = last.get("ipynb_version") if isinstance(last, dict) else None
    last_t = last.get("text_version") if isinstance(last, dict) else None
    conflict = False
    source = "none"
    planned: list[str] = []
    if not exists["ipynb"] and not exists["text"]:
        errors.append("both sides of pair are missing")
    elif errors:
        source = "none"
    elif not exists["ipynb"]:
        source = "text"
        planned = [paths["ipynb"], STATE_NAME]
    elif not exists["text"]:
        source = "ipynb"
        planned = [paths["text"], STATE_NAME]
    elif entry is None:
        source = "none"
        errors.append("missing state entry")
    else:
        changed_i = isinstance(ipynb_version, int) and isinstance(last_i, int) and ipynb_version > last_i
        changed_t = isinstance(text_version, int) and isinstance(last_t, int) and text_version > last_t
        if changed_i and changed_t:
            conflict = True
            source = "none"
        elif changed_i:
            source = "ipynb"
            planned = [paths["text"], STATE_NAME]
        elif changed_t:
            source = "text"
            planned = [paths["ipynb"], STATE_NAME]

    differences: list[str] = []
    roundtrip_ok = True
    if check or (ipynb_model is not None and text_model is not None):
        if ipynb_model is None or text_model is None:
            differences.append("missing")
            roundtrip_ok = False
        else:
            differences = compare_models(ipynb_model, text_model)
            if output_differences_after_preservation(ipynb_model, text_model):
                differences.append("outputs")
            if isinstance(last_i, int) and isinstance(ipynb_version, int) and last_i > ipynb_version:
                differences.append("state")
            if isinstance(last_t, int) and isinstance(text_version, int) and last_t > text_version:
                differences.append("state")
            if check and entry is None:
                differences.append("state")
            differences = sorted(set(differences))
            roundtrip_ok = not differences
    elif missing:
        roundtrip_ok = False
        differences = ["missing"]

    versions = {
        "ipynb": ipynb_version,
        "text": text_version,
        "last_ipynb": last_i,
        "last_text": last_t,
    }
    return {
        "ipynb": paths["ipynb"],
        "text": paths["text"],
        "exists": exists,
        "versions": versions,
        "source": source,
        "conflict": conflict,
        "missing": missing,
        "planned_writes": planned,
        "roundtrip_ok": roundtrip_ok,
        "differences": differences,
        "errors": errors,
    }


def status_response(command: str, pairs: list[dict[str, Any]], config: Config) -> dict[str, Any]:
    return {
        "ok": True,
        "command": command,
        "root": root_label(config.root),
        "pairs": pairs,
        "summary": summarize(pairs),
    }


def discover_pairs(config: Config) -> list[dict[str, Any]]:
    if not config.config_path:
        raise MiniJupyError("--all requires --config")
    roots: list[Path]
    if config.notebook_dir is not None and config.script_dir is not None:
        roots = [config.root / config.notebook_dir, config.root / config.script_dir]
    else:
        roots = [config.root]
    by_key: dict[str, dict[str, Any]] = {}
    text_to_key: dict[str, str] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in {".ipynb", ".py"}:
                continue
            paths = pair_paths(path, config)
            key = paths["key"]
            if key in by_key:
                if by_key[key]["text"] != paths["text"]:
                    raise MiniJupyError("duplicate paired paths")
            else:
                by_key[key] = paths
            existing = text_to_key.get(paths["text"])
            if existing is not None and existing != key:
                raise MiniJupyError("duplicate paired paths")
            text_to_key[paths["text"]] = key
    return [by_key[key] for key in sorted(by_key)]


def ensure_input_output(input_path: Path, output_path: Path, wanted_in: str, wanted_out: str) -> None:
    if input_path.suffix != wanted_in or output_path.suffix != wanted_out:
        raise MiniJupyError("unsupported input or output extension")


def command_inspect(args: argparse.Namespace) -> dict[str, Any]:
    config = Config(Path(args.config) if args.config else None)
    path = Path(args.input).resolve()
    model = read_model(path)
    fmt = "ipynb" if path.suffix == ".ipynb" else "py:percent"
    return {
        "ok": True,
        "command": "inspect",
        "path": rel_display(path, config.root),
        "format": fmt,
        "version": model_version(model),
        "notebook": model,
    }


def command_paths(args: argparse.Namespace) -> dict[str, Any]:
    config = Config(Path(args.config) if args.config else None)
    paths = pair_paths(Path(args.input).resolve(), config)
    return {
        "ok": True,
        "command": "paths",
        "root": root_label(config.root),
        "input": paths["input"],
        "ipynb": paths["ipynb"],
        "text": paths["text"],
        "exists": {
            "ipynb": paths["ipynb_path"].exists(),
            "text": paths["text_path"].exists(),
        },
    }


def command_to_text(args: argparse.Namespace) -> dict[str, Any]:
    config = Config(Path(args.config) if args.config else None)
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    ensure_input_output(input_path, output_path, ".ipynb", ".py")
    model = read_model(input_path)
    atomic_write_text(output_path, write_percent_model(model))
    return {
        "ok": True,
        "command": "to-text",
        "input": rel_display(input_path, config.root),
        "output": rel_display(output_path, config.root),
        "written": [rel_display(output_path, config.root)],
    }


def command_to_ipynb(args: argparse.Namespace) -> dict[str, Any]:
    config = Config(Path(args.config) if args.config else None)
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    ensure_input_output(input_path, output_path, ".py", ".ipynb")
    model = read_model(input_path)
    if args.update and output_path.exists():
        model = preserve_outputs(model, read_model(output_path))
    atomic_write_text(output_path, write_ipynb_model(model))
    return {
        "ok": True,
        "command": "to-ipynb",
        "input": rel_display(input_path, config.root),
        "output": rel_display(output_path, config.root),
        "written": [rel_display(output_path, config.root)],
    }


def command_pair(args: argparse.Namespace) -> dict[str, Any]:
    config = Config(Path(args.config) if args.config else None)
    paths = pair_paths(Path(args.input).resolve(), config)
    ipynb_exists = paths["ipynb_path"].exists()
    text_exists = paths["text_path"].exists()
    if not ipynb_exists and not text_exists:
        raise MiniJupyError("both sides of pair are missing")
    written: list[str] = []
    old_ipynb: dict[str, Any] | None = read_model(paths["ipynb_path"]) if ipynb_exists else None
    old_text: dict[str, Any] | None = read_model(paths["text_path"]) if text_exists else None

    if old_ipynb is None and old_text is not None:
        text_model = set_formats(old_text)
        ipynb_model = copy.deepcopy(text_model)
    elif old_ipynb is not None and old_text is None:
        ipynb_model = set_formats(old_ipynb)
        text_model = text_representable_model(ipynb_model)
    else:
        assert old_ipynb is not None and old_text is not None
        ipynb_model = set_formats(old_ipynb)
        text_model = set_formats(old_text)

    atomic_write_text(paths["ipynb_path"], write_ipynb_model(ipynb_model))
    written.append(paths["ipynb"])
    atomic_write_text(paths["text_path"], write_percent_model(text_model))
    written.append(paths["text"])
    state = load_state(config)
    state["pairs"][paths["key"]] = state_entry(paths["ipynb"], paths["text"], ipynb_model, text_model)
    write_state(config, state)
    written.append(STATE_NAME)
    return {
        "ok": True,
        "command": "pair",
        "root": root_label(config.root),
        "ipynb": paths["ipynb"],
        "text": paths["text"],
        "written": written,
    }


def command_status_or_check(args: argparse.Namespace, command: str) -> dict[str, Any]:
    config = Config(Path(args.config) if args.config else None)
    state = load_state(config)
    if args.all:
        paths_list = discover_pairs(config)
    else:
        paths_list = [pair_paths(Path(args.input).resolve(), config)]
    pairs = [pair_status(paths, config, state, check=(command == "check")) for paths in paths_list]
    return status_response(command, pairs, config)


def choose_sync_source(
    pair: dict[str, Any], paths: dict[str, Any], explicit: str | None, state: dict[str, Any]
) -> str:
    if explicit:
        if explicit == "ipynb" and not paths["ipynb_path"].exists():
            raise MiniJupyError("explicit ipynb source is missing")
        if explicit == "text" and not paths["text_path"].exists():
            raise MiniJupyError("explicit text source is missing")
        return explicit
    if pair["conflict"]:
        raise MiniJupyError("conflict without explicit --source")
    if pair["errors"]:
        raise MiniJupyError("; ".join(pair["errors"]))
    if pair["source"] == "none" and paths["ipynb_path"].exists() and paths["text_path"].exists():
        if paths["key"] not in state.get("pairs", {}):
            raise MiniJupyError("both sides exist without state; run pair or pass --source")
    return pair["source"]


def build_sync_plan(
    paths: dict[str, Any], config: Config, state: dict[str, Any], explicit: str | None = None
) -> tuple[dict[str, Any], list[tuple[Path, str]], dict[str, Any]]:
    pair = pair_status(paths, config, state, check=True)
    source = choose_sync_source(pair, paths, explicit, state)
    writes: list[tuple[Path, str]] = []
    new_state = copy.deepcopy(state)
    pair["source"] = source
    if source == "none":
        pair["planned_writes"] = []
        return pair, writes, new_state

    if source == "ipynb":
        src = set_formats(read_model(paths["ipynb_path"]))
        dst = text_representable_model(src)
        writes.append((paths["text_path"], write_percent_model(dst)))
        ipynb_model = src
        text_model = dst
        pair["planned_writes"] = [paths["text"], STATE_NAME]
    elif source == "text":
        src = set_formats(read_model(paths["text_path"]))
        old_ipynb = read_model(paths["ipynb_path"]) if paths["ipynb_path"].exists() else None
        dst = preserve_outputs(copy.deepcopy(src), old_ipynb)
        writes.append((paths["ipynb_path"], write_ipynb_model(dst)))
        ipynb_model = dst
        text_model = src
        pair["planned_writes"] = [paths["ipynb"], STATE_NAME]
    else:
        raise MiniJupyError("invalid sync source")
    new_state["pairs"][paths["key"]] = state_entry(paths["ipynb"], paths["text"], ipynb_model, text_model)
    return pair, writes, new_state


def command_sync(args: argparse.Namespace) -> dict[str, Any]:
    config = Config(Path(args.config) if args.config else None)
    state = load_state(config)
    if args.all:
        paths_list = discover_pairs(config)
    else:
        paths_list = [pair_paths(Path(args.input).resolve(), config)]

    all_pairs: list[dict[str, Any]] = []
    all_writes: list[tuple[Path, str]] = []
    new_state = copy.deepcopy(state)
    for paths in paths_list:
        pair, writes, new_state = build_sync_plan(paths, config, new_state, args.source)
        all_pairs.append(pair)
        all_writes.extend(writes)

    for path, text in all_writes:
        atomic_write_text(path, text)
    if any(pair.get("source") != "none" for pair in all_pairs):
        write_state(config, new_state)
    return status_response("sync", all_pairs, config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minijupy.py")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser, input_arg: bool = True) -> None:
        if input_arg:
            p.add_argument("--input")
        p.add_argument("--config")

    p = sub.add_parser("inspect")
    add_common(p)
    p.set_defaults(func=command_inspect)

    p = sub.add_parser("paths")
    add_common(p)
    p.set_defaults(func=command_paths)

    p = sub.add_parser("to-text")
    add_common(p)
    p.add_argument("--output")
    p.set_defaults(func=command_to_text)

    p = sub.add_parser("to-ipynb")
    add_common(p)
    p.add_argument("--output")
    p.add_argument("--update", action="store_true")
    p.set_defaults(func=command_to_ipynb)

    p = sub.add_parser("pair")
    add_common(p)
    p.set_defaults(func=command_pair)

    for name in ("status", "check"):
        p = sub.add_parser(name)
        p.add_argument("--input")
        p.add_argument("--all", action="store_true")
        p.add_argument("--config")
        p.set_defaults(func=lambda ns, command=name: command_status_or_check(ns, command))

    p = sub.add_parser("sync")
    p.add_argument("--input")
    p.add_argument("--all", action="store_true")
    p.add_argument("--config")
    p.add_argument("--source", choices=["ipynb", "text"])
    p.set_defaults(func=command_sync)
    return parser


def validate_args(args: argparse.Namespace) -> None:
    command = args.command
    if command in {"inspect", "paths", "pair"} and not args.input:
        raise MiniJupyError("--input is required")
    if command in {"to-text", "to-ipynb"}:
        if not args.input or not args.output:
            raise MiniJupyError("--input and --output are required")
    if command in {"status", "check", "sync"}:
        if args.all:
            if not args.config:
                raise MiniJupyError("--all requires --config")
            if args.input:
                raise MiniJupyError("--input cannot be combined with --all")
        elif not args.input:
            raise MiniJupyError("--input is required")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(args)
        result = args.func(args)
    except MiniJupyError as exc:
        return fail(str(exc))
    print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

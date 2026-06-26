#!/usr/bin/env python3
"""Mini Jupytext paired-notebook CLI."""

from __future__ import annotations

import argparse
import ast
import copy
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FORMAT = "ipynb,py:percent"
SUPPORTED_NOTEBOOK_METADATA = {"minijupy", "kernelspec"}
SUPPORTED_CELL_METADATA = {"tags", "name"}


class MiniJupyError(Exception):
    """User-facing command error."""


@dataclass
class Config:
    formats: str = FORMAT
    notebook_dir: str = ""
    script_dir: str = ""
    base_dir: Path = Path.cwd()

    @property
    def mapping_active(self) -> bool:
        return bool(self.notebook_dir and self.script_dir)


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def print_json(value: Any) -> None:
    sys.stdout.write(compact_json(value) + "\n")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise MiniJupyError(f"input file does not exist: {path}") from None
    except OSError as exc:
        raise MiniJupyError(f"could not read {path}: {exc}") from exc


def parse_config_value(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise MiniJupyError("invalid config value")
    if raw[0] in {"'", '"'}:
        try:
            value = ast.literal_eval(raw)
        except (SyntaxError, ValueError) as exc:
            raise MiniJupyError("invalid config value") from exc
    else:
        value = raw
    if not isinstance(value, str):
        raise MiniJupyError("invalid config value")
    if "\n" in value or "\r" in value:
        raise MiniJupyError("invalid config value")
    return value


def load_config(input_path: Path, config_arg: str | None) -> Config:
    config_path = Path(config_arg) if config_arg else input_path.parent / "minijupy.toml"
    exists = config_path.exists()
    base_dir = config_path.parent if exists else Path.cwd()
    cfg = Config(base_dir=base_dir)
    if not exists:
        return cfg

    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise MiniJupyError(f"could not read config {config_path}: {exc}") from exc

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise MiniJupyError(f"invalid config line {lineno}")
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if key not in {"formats", "notebook_dir", "script_dir"}:
            continue
        value = parse_config_value(raw_value)
        if key == "formats":
            cfg.formats = value
        elif key == "notebook_dir":
            cfg.notebook_dir = value.strip("/")
        elif key == "script_dir":
            cfg.script_dir = value.strip("/")

    validate_formats(cfg.formats)
    return cfg


def validate_formats(formats: str) -> None:
    if formats != FORMAT:
        raise MiniJupyError(f"unsupported formats value: {formats}")


def file_format(path: Path) -> str:
    if path.suffix == ".ipynb":
        return "ipynb"
    if path.suffix == ".py":
        return "text"
    raise MiniJupyError(f"unsupported file extension: {path}")


def absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def relative_to_root(path: Path, root: Path) -> Path:
    path_abs = absolute_lexical(path)
    root_abs = absolute_lexical(root)
    try:
        return path_abs.relative_to(root_abs)
    except ValueError as exc:
        raise MiniJupyError(f"{path} is not under configured directory {root}") from exc


def paired_paths(input_path: Path, cfg: Config) -> tuple[Path, Path]:
    validate_formats(cfg.formats)
    fmt = file_format(input_path)
    if not cfg.mapping_active:
        if fmt == "ipynb":
            return input_path, input_path.with_suffix(".py")
        return input_path.with_suffix(".ipynb"), input_path

    nb_root = cfg.base_dir / cfg.notebook_dir
    py_root = cfg.base_dir / cfg.script_dir
    if fmt == "ipynb":
        rel = relative_to_root(input_path, nb_root)
        if rel.suffix != ".ipynb":
            raise MiniJupyError(f"unsupported file extension: {input_path}")
        return nb_root / rel, py_root / rel.with_suffix(".py")
    rel = relative_to_root(input_path, py_root)
    if rel.suffix != ".py":
        raise MiniJupyError(f"unsupported file extension: {input_path}")
    return nb_root / rel.with_suffix(".ipynb"), py_root / rel


def json_copy(value: Any) -> Any:
    return copy.deepcopy(value)


def warning(warnings: list[str] | None, message: str) -> None:
    if warnings is not None:
        warnings.append(message)


def normalize_minijupy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MiniJupyError("metadata.minijupy must be an object")
    out: dict[str, Any] = {}
    if "formats" in value:
        if not isinstance(value["formats"], str):
            raise MiniJupyError("metadata.minijupy.formats must be a string")
        validate_formats(value["formats"])
        out["formats"] = value["formats"]
    if "version" in value:
        version = value["version"]
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise MiniJupyError("metadata.minijupy.version must be a non-negative integer")
        out["version"] = version
    return out


def normalize_notebook_metadata(raw: Any, warnings: list[str] | None) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise MiniJupyError("notebook metadata must be an object")

    out: dict[str, Any] = {}
    for key in sorted(raw):
        if key not in SUPPORTED_NOTEBOOK_METADATA:
            warning(warnings, f"unsupported-notebook-metadata:{key}")

    if "minijupy" in raw:
        out["minijupy"] = normalize_minijupy(raw["minijupy"])
    if "kernelspec" in raw:
        if not isinstance(raw["kernelspec"], dict):
            raise MiniJupyError("metadata.kernelspec must be an object")
        out["kernelspec"] = json_copy(raw["kernelspec"])
    return out


def normalize_cell_metadata(raw: Any, warnings: list[str] | None) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise MiniJupyError("cell metadata must be an object")

    out: dict[str, Any] = {}
    for key in sorted(raw):
        if key not in SUPPORTED_CELL_METADATA:
            warning(warnings, f"unsupported-cell-metadata:{key}")

    if "tags" in raw:
        tags = raw["tags"]
        if isinstance(tags, list) and all(isinstance(tag, str) for tag in tags):
            out["tags"] = list(tags)
        else:
            raise MiniJupyError("cell metadata tags must be an array of strings")
    if "name" in raw:
        name = raw["name"]
        if isinstance(name, str):
            out["name"] = name
        else:
            raise MiniJupyError("cell metadata name must be a string")
    return out


def normalize_source(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list) and all(isinstance(part, str) for part in raw):
        return "".join(raw)
    raise MiniJupyError("cell source must be a string")


def make_cell(
    *,
    cell_id: str,
    cell_type: str,
    source: str,
    metadata: dict[str, Any],
    execution_count: Any = None,
    outputs: Any = None,
    id_stable: bool = True,
) -> dict[str, Any]:
    if cell_type not in {"code", "markdown", "raw"}:
        raise MiniJupyError(f"unsupported cell_type: {cell_type}")
    if not isinstance(cell_id, str) or not cell_id:
        raise MiniJupyError("cell id must be a non-empty string")
    if cell_type == "code":
        cell_outputs = outputs if isinstance(outputs, list) else []
        return {
            "id": cell_id,
            "cell_type": cell_type,
            "source": source,
            "metadata": metadata,
            "execution_count": execution_count,
            "outputs": json_copy(cell_outputs),
            "_id_stable": id_stable,
        }
    return {
        "id": cell_id,
        "cell_type": cell_type,
        "source": source,
        "metadata": metadata,
        "execution_count": None,
        "outputs": [],
        "_id_stable": id_stable,
    }


def check_duplicate_ids(cells: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for cell in cells:
        cell_id = cell["id"]
        if cell_id in seen:
            raise MiniJupyError(f"duplicate cell id: {cell_id}")
        seen.add(cell_id)


def parse_ipynb(path: Path, warnings: list[str] | None = None) -> dict[str, Any]:
    text = read_text(path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed .ipynb JSON: {path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise MiniJupyError(".ipynb root must be an object")

    metadata = normalize_notebook_metadata(data.get("metadata", {}), warnings)
    raw_cells = data.get("cells", [])
    if not isinstance(raw_cells, list):
        raise MiniJupyError(".ipynb cells must be an array")

    cells: list[dict[str, Any]] = []
    for index, raw_cell in enumerate(raw_cells, start=1):
        if not isinstance(raw_cell, dict):
            raise MiniJupyError("cell must be an object")
        cell_type = raw_cell.get("cell_type")
        if not isinstance(cell_type, str):
            raise MiniJupyError("cell_type must be a string")
        raw_id = raw_cell.get("id")
        id_stable = isinstance(raw_id, str) and bool(raw_id)
        cell_id = raw_id if id_stable else f"c{index}"
        cell = make_cell(
            cell_id=cell_id,
            cell_type=cell_type,
            source=normalize_source(raw_cell.get("source", "")),
            metadata=normalize_cell_metadata(raw_cell.get("metadata", {}), warnings),
            execution_count=raw_cell.get("execution_count"),
            outputs=raw_cell.get("outputs", []),
            id_stable=id_stable,
        )
        cells.append(cell)
    check_duplicate_ids(cells)
    return {"metadata": metadata, "cells": cells}


HEADER_RE = re.compile(r"^# ([A-Za-z0-9_]+): (.*)$")


def parse_header(lines: list[str], warnings: list[str] | None) -> tuple[dict[str, Any], int]:
    if not lines or lines[0] != "# ---":
        return {}, 0

    metadata: dict[str, Any] = {}
    index = 1
    while index < len(lines) and lines[index] != "# ---":
        match = HEADER_RE.match(lines[index])
        if not match:
            raise MiniJupyError("malformed percent script header")
        key, raw_json = match.groups()
        if key not in {"minijupy", "kernelspec"}:
            warning(warnings, f"unsupported-header:{key}")
            index += 1
            continue
        try:
            value = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise MiniJupyError(f"malformed JSON in header key {key}") from exc
        if key == "minijupy":
            metadata["minijupy"] = normalize_minijupy(value)
        elif key == "kernelspec":
            if not isinstance(value, dict):
                raise MiniJupyError("header kernelspec must be an object")
            metadata["kernelspec"] = value
        index += 1

    if index >= len(lines) or lines[index] != "# ---":
        raise MiniJupyError("malformed percent script header")
    return metadata, index + 1


def parse_marker(line: str, warnings: list[str] | None) -> tuple[str, dict[str, Any]]:
    if not line.startswith("# %%"):
        raise MiniJupyError("expected cell marker")

    rest = line[len("# %%") :]
    cell_type = "code"
    marker: dict[str, Any] = {}

    if rest:
        if not rest.startswith(" "):
            raise MiniJupyError(f"malformed cell marker: {line}")
        token = rest[1:]
        raw_json: str | None = None
        if token.startswith("[markdown]"):
            cell_type = "markdown"
            token = token[len("[markdown]") :]
        elif token.startswith("[raw]"):
            cell_type = "raw"
            token = token[len("[raw]") :]

        if token:
            if cell_type == "code":
                raw_json = token
            elif token.startswith(" "):
                raw_json = token[1:]
            else:
                raise MiniJupyError(f"malformed cell marker: {line}")
        if raw_json is not None:
            try:
                parsed = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                raise MiniJupyError("malformed cell metadata JSON") from exc
            if not isinstance(parsed, dict):
                raise MiniJupyError("cell marker metadata must be an object")
            for key in sorted(parsed):
                if key not in {"id", "tags", "name"}:
                    warning(warnings, f"unsupported-marker-field:{key}")
            if "id" in parsed:
                if not isinstance(parsed["id"], str) or not parsed["id"]:
                    raise MiniJupyError("cell marker id must be a non-empty string")
                marker["id"] = parsed["id"]
            if "tags" in parsed:
                tags = parsed["tags"]
                if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
                    raise MiniJupyError("cell marker tags must be an array of strings")
                marker["tags"] = list(tags)
            if "name" in parsed:
                if not isinstance(parsed["name"], str):
                    raise MiniJupyError("cell marker name must be a string")
                marker["name"] = parsed["name"]

    return cell_type, marker


def is_marker(line: str) -> bool:
    return line.startswith("# %%")


def decode_body(cell_type: str, body_lines: list[str]) -> str:
    if cell_type == "code":
        return "\n".join(body_lines)

    decoded: list[str] = []
    for line in body_lines:
        if line == "#":
            decoded.append("")
        elif line.startswith("# "):
            decoded.append(line[2:])
        else:
            raise MiniJupyError("malformed markdown/raw cell body")
    return "\n".join(decoded)


def parse_text_script(path: Path, warnings: list[str] | None = None) -> dict[str, Any]:
    text = read_text(path)
    lines = text.splitlines()
    metadata, index = parse_header(lines, warnings)

    while index < len(lines) and lines[index] == "":
        index += 1

    cells: list[dict[str, Any]] = []
    cell_index = 1
    while index < len(lines):
        if not is_marker(lines[index]):
            raise MiniJupyError("malformed percent script")
        cell_type, marker = parse_marker(lines[index], warnings)
        index += 1
        body_start = index
        while index < len(lines) and not is_marker(lines[index]):
            index += 1
        body_lines = lines[body_start:index]
        if index < len(lines) and body_lines and body_lines[-1] == "":
            body_lines = body_lines[:-1]

        id_stable = "id" in marker
        cell_id = marker.get("id", f"c{cell_index}")
        cell_metadata: dict[str, Any] = {}
        if "tags" in marker:
            cell_metadata["tags"] = marker["tags"]
        if "name" in marker:
            cell_metadata["name"] = marker["name"]
        cells.append(
            make_cell(
                cell_id=cell_id,
                cell_type=cell_type,
                source=decode_body(cell_type, body_lines),
                metadata=cell_metadata,
                execution_count=None,
                outputs=[],
                id_stable=id_stable,
            )
        )
        cell_index += 1

    check_duplicate_ids(cells)
    return {"metadata": metadata, "cells": cells}


def parse_model(path: Path, warnings: list[str] | None = None) -> dict[str, Any]:
    fmt = file_format(path)
    if fmt == "ipynb":
        return parse_ipynb(path, warnings)
    return parse_text_script(path, warnings)


def get_version(model: dict[str, Any]) -> int:
    minijupy = model.get("metadata", {}).get("minijupy", {})
    version = minijupy.get("version", 0) if isinstance(minijupy, dict) else 0
    return version if isinstance(version, int) and not isinstance(version, bool) else 0


def get_formats(model: dict[str, Any], cfg: Config | None = None) -> str:
    minijupy = model.get("metadata", {}).get("minijupy", {})
    if isinstance(minijupy, dict) and isinstance(minijupy.get("formats"), str):
        validate_formats(minijupy["formats"])
        return minijupy["formats"]
    return cfg.formats if cfg else FORMAT


def clone_model(model: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(model)


def with_minijupy(model: dict[str, Any], formats: str, version: int) -> dict[str, Any]:
    validate_formats(formats)
    if version < 0:
        raise MiniJupyError("version must be a non-negative integer")
    cloned = clone_model(model)
    metadata = cloned.setdefault("metadata", {})
    ordered_metadata: dict[str, Any] = {"minijupy": {"formats": formats, "version": version}}
    if "kernelspec" in metadata:
        ordered_metadata["kernelspec"] = metadata["kernelspec"]
    cloned["metadata"] = ordered_metadata
    return cloned


def cell_public_metadata(cell: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    raw = cell.get("metadata", {})
    if "tags" in raw:
        metadata["tags"] = list(raw["tags"])
    if "name" in raw:
        metadata["name"] = raw["name"]
    return metadata


def serializable_cells(model: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cell in model["cells"]:
        cell_type = cell["cell_type"]
        item = {
            "id": cell["id"],
            "cell_type": cell_type,
            "source": cell["source"],
            "metadata": cell_public_metadata(cell),
            "execution_count": cell.get("execution_count") if cell_type == "code" else None,
            "outputs": json_copy(cell.get("outputs", [])) if cell_type == "code" else [],
        }
        out.append(item)
    return out


def render_ipynb(model: dict[str, Any]) -> str:
    data = {
        "metadata": json_copy(model.get("metadata", {})),
        "cells": serializable_cells(model),
    }
    return compact_json(data) + "\n"


def metadata_for_header(metadata: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if "minijupy" in metadata:
        lines.append(f"# minijupy: {compact_json(metadata['minijupy'])}")
    if "kernelspec" in metadata:
        lines.append(f"# kernelspec: {compact_json(metadata['kernelspec'])}")
    return lines


def encode_body(cell: dict[str, Any]) -> list[str]:
    source = cell["source"]
    if source == "":
        parts: list[str] = []
    else:
        parts = source.split("\n")

    if cell["cell_type"] == "code":
        return parts
    encoded: list[str] = []
    for part in parts:
        encoded.append("#" if part == "" else f"# {part}")
    return encoded


def render_text(model: dict[str, Any]) -> str:
    lines: list[str] = []
    header_body = metadata_for_header(model.get("metadata", {}))
    if header_body:
        lines.append("# ---")
        lines.extend(header_body)
        lines.append("# ---")

    for index, cell in enumerate(model["cells"]):
        if lines and index == 0:
            pass
        marker = "# %%"
        if cell["cell_type"] == "markdown":
            marker += " [markdown]"
        elif cell["cell_type"] == "raw":
            marker += " [raw]"
        marker_fields: dict[str, Any] = {"id": cell["id"]}
        metadata = cell_public_metadata(cell)
        if "tags" in metadata:
            marker_fields["tags"] = metadata["tags"]
        if "name" in metadata:
            marker_fields["name"] = metadata["name"]
        marker += " " + compact_json(marker_fields)
        lines.append(marker)
        lines.extend(encode_body(cell))
        if index != len(model["cells"]) - 1:
            lines.append("")
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def stage_write(path: Path, content: str, temp_paths: list[Path]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    temp_paths.append(temp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    return temp_path


def restore_path(path: Path, original: bytes | None) -> None:
    if original is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.restore.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(original)
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def write_many_atomic(writes: dict[Path, str]) -> None:
    if not writes:
        return

    originals: dict[Path, bytes | None] = {}
    temp_paths: list[Path] = []
    staged: list[tuple[Path, Path]] = []
    replaced: list[Path] = []
    try:
        for path in writes:
            originals[path] = path.read_bytes() if path.exists() else None
        for path, content in writes.items():
            staged.append((path, stage_write(path, content, temp_paths)))
        for path, temp_path in staged:
            os.replace(temp_path, path)
            replaced.append(path)
    except Exception as exc:
        for path in reversed(replaced):
            restore_path(path, originals[path])
        for temp_path in temp_paths:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        raise MiniJupyError(f"could not write output atomically: {exc}") from exc


def inspect_cells(model: dict[str, Any]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for cell in model["cells"]:
        cells.append(
            {
                "id": cell["id"],
                "cell_type": cell["cell_type"],
                "source": cell["source"],
                "metadata": cell_public_metadata(cell),
                "execution_count": cell.get("execution_count") if cell["cell_type"] == "code" else None,
                "has_outputs": bool(cell.get("outputs")) if cell["cell_type"] == "code" else False,
            }
        )
    return cells


def source_needs_minijupy_write(model: dict[str, Any], formats: str, version: int) -> bool:
    metadata = model.get("metadata", {})
    return metadata.get("minijupy") != {"formats": formats, "version": version}


def merge_ipynb_outputs(source_model: dict[str, Any], existing_ipynb: dict[str, Any] | None) -> dict[str, Any]:
    merged = clone_model(source_model)
    if existing_ipynb is None:
        return merged

    existing_cells = existing_ipynb["cells"]
    any_stable_ids = any(cell.get("_id_stable") for cell in source_model["cells"])
    by_id = {cell["id"]: cell for cell in existing_cells}

    for index, cell in enumerate(merged["cells"]):
        if cell["cell_type"] != "code":
            cell["execution_count"] = None
            cell["outputs"] = []
            continue

        previous: dict[str, Any] | None = None
        if any_stable_ids:
            previous = by_id.get(cell["id"])
        elif index < len(existing_cells):
            previous = existing_cells[index]

        if previous and previous.get("cell_type") == "code":
            cell["execution_count"] = previous.get("execution_count")
            cell["outputs"] = json_copy(previous.get("outputs", []))
        else:
            cell["execution_count"] = None
            cell["outputs"] = []
    return merged


def text_comparison_projection(model: dict[str, Any]) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for cell in model["cells"]:
        cells.append(
            {
                "id": cell["id"],
                "cell_type": cell["cell_type"],
                "source": cell["source"],
                "metadata": cell_public_metadata(cell),
            }
        )
    return {"metadata": json_copy(model.get("metadata", {})), "cells": cells}


def compare_text_representable(ipynb_model: dict[str, Any], text_model: dict[str, Any]) -> tuple[bool, list[str]]:
    left = text_comparison_projection(ipynb_model)
    right = text_comparison_projection(text_model)
    differences: list[str] = []

    if left["metadata"] != right["metadata"]:
        differences.append("metadata")

    left_cells = left["cells"]
    right_cells = right["cells"]
    if len(left_cells) != len(right_cells):
        differences.append("cell-count")

    left_ids = [cell["id"] for cell in left_cells]
    right_ids = [cell["id"] for cell in right_cells]
    if left_ids != right_ids and sorted(left_ids) == sorted(right_ids):
        differences.append("cell-order")

    for left_cell, right_cell in zip(left_cells, right_cells):
        if left_cell["cell_type"] != right_cell["cell_type"] and "cell-type" not in differences:
            differences.append("cell-type")
        if left_cell["source"] != right_cell["source"] and "cell-source" not in differences:
            differences.append("cell-source")
        left_tags = left_cell["metadata"].get("tags", [])
        right_tags = right_cell["metadata"].get("tags", [])
        if left_tags != right_tags and "cell-tags" not in differences:
            differences.append("cell-tags")
        left_name = left_cell["metadata"].get("name")
        right_name = right_cell["metadata"].get("name")
        if left_name != right_name and "cell-name" not in differences:
            differences.append("cell-name")

    return not differences, differences


def command_inspect(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if not input_path.exists():
        raise MiniJupyError(f"input file does not exist: {input_path}")
    cfg = load_config(input_path, args.config)
    ipynb_path, py_path = paired_paths(input_path, cfg)
    warnings: list[str] = []
    model = parse_model(input_path, warnings)
    print_json(
        {
            "input": str(input_path),
            "format": file_format(input_path),
            "paired_paths": [str(ipynb_path), str(py_path)],
            "version": get_version(model),
            "formats": get_formats(model, cfg),
            "cells": inspect_cells(model),
            "warnings": warnings,
        }
    )


def command_to_text(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)
    if input_path.suffix != ".ipynb":
        raise MiniJupyError("to-text input must be .ipynb")
    model = parse_ipynb(input_path)
    write_many_atomic({output_path: render_text(model)})
    print_json({"written": str(output_path), "cells": len(model["cells"])})


def command_to_ipynb(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)
    if input_path.suffix != ".py":
        raise MiniJupyError("to-ipynb input must be .py")
    model = parse_text_script(input_path)
    write_many_atomic({output_path: render_ipynb(model)})
    print_json({"written": str(output_path), "cells": len(model["cells"])})


def command_pair(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if input_path.suffix != ".ipynb":
        raise MiniJupyError("pair input must be .ipynb")
    validate_formats(args.formats)
    if not input_path.exists():
        raise MiniJupyError(f"input file does not exist: {input_path}")
    cfg = load_config(input_path, args.config)
    ipynb_path, py_path = paired_paths(input_path, cfg)
    model = parse_ipynb(input_path)
    version = get_version(model)
    paired_model = with_minijupy(model, args.formats, version)
    write_many_atomic({ipynb_path: render_ipynb(paired_model), py_path: render_text(paired_model)})
    print_json({"paired_paths": [str(ipynb_path), str(py_path)], "version": version})


def parse_existing(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return parse_model(path)


def command_sync(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if not input_path.exists():
        raise MiniJupyError(f"input file does not exist: {input_path}")
    cfg = load_config(input_path, args.config)
    ipynb_path, py_path = paired_paths(input_path, cfg)

    ipynb_model = parse_existing(ipynb_path)
    text_model = parse_existing(py_path)
    ipynb_exists = ipynb_model is not None
    text_exists = text_model is not None

    source = args.source
    if source is None:
        if ipynb_exists and not text_exists:
            source = "ipynb"
        elif text_exists and not ipynb_exists:
            source = "text"
        elif ipynb_exists and text_exists:
            ipynb_version = get_version(ipynb_model)
            text_version = get_version(text_model)
            if ipynb_version > text_version:
                source = "ipynb"
            elif text_version > ipynb_version:
                source = "text"
            else:
                print_json({"source": "none", "wrote": [], "version": ipynb_version, "synced": True})
                return
        else:
            raise MiniJupyError("no paired representation exists")

    if source == "ipynb":
        if ipynb_model is None:
            raise MiniJupyError(f"source file does not exist: {ipynb_path}")
        source_model = ipynb_model
        version = get_version(source_model)
        formats = get_formats(source_model, cfg)
        synced_model = with_minijupy(source_model, formats, version)
        writes: dict[Path, str] = {py_path: render_text(synced_model)}
        if source_needs_minijupy_write(source_model, formats, version):
            writes[ipynb_path] = render_ipynb(synced_model)
    elif source == "text":
        if text_model is None:
            raise MiniJupyError(f"source file does not exist: {py_path}")
        source_model = text_model
        version = get_version(source_model)
        formats = get_formats(source_model, cfg)
        synced_model = with_minijupy(source_model, formats, version)
        ipynb_with_outputs = merge_ipynb_outputs(synced_model, ipynb_model)
        writes = {ipynb_path: render_ipynb(ipynb_with_outputs)}
        if source_needs_minijupy_write(source_model, formats, version):
            writes[py_path] = render_text(synced_model)
    else:
        raise MiniJupyError(f"invalid source value: {source}")

    write_many_atomic(writes)
    print_json({"source": source, "wrote": [str(path) for path in writes], "version": version, "synced": True})


def status_with_parse_errors(
    ipynb_path: Path,
    py_path: Path,
    ipynb_error: str | None,
    text_error: str | None,
    missing: list[str],
) -> None:
    errors = []
    if ipynb_error:
        errors.append(f"ipynb:{ipynb_error}")
    if text_error:
        errors.append(f"text:{text_error}")
    print_json(
        {
            "paired_paths": [str(ipynb_path), str(py_path)],
            "source": "none",
            "would_write": [],
            "roundtrip_ok": False,
            "differences": [],
            "missing": missing,
            "errors": errors,
        }
    )


def command_status(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if not input_path.exists():
        raise MiniJupyError(f"input file does not exist: {input_path}")
    cfg = load_config(input_path, args.config)
    ipynb_path, py_path = paired_paths(input_path, cfg)

    missing = [str(path) for path in (ipynb_path, py_path) if not path.exists()]
    ipynb_model: dict[str, Any] | None = None
    text_model: dict[str, Any] | None = None
    ipynb_error: str | None = None
    text_error: str | None = None

    if ipynb_path.exists():
        try:
            ipynb_model = parse_ipynb(ipynb_path)
        except MiniJupyError as exc:
            ipynb_error = str(exc)
    if py_path.exists():
        try:
            text_model = parse_text_script(py_path)
        except MiniJupyError as exc:
            text_error = str(exc)

    if ipynb_error or text_error:
        input_fmt = file_format(input_path)
        if input_fmt == "ipynb" and ipynb_error:
            raise MiniJupyError(ipynb_error)
        if input_fmt == "text" and text_error:
            raise MiniJupyError(text_error)
        status_with_parse_errors(ipynb_path, py_path, ipynb_error, text_error, missing)
        return

    if ipynb_model is None and text_model is None:
        raise MiniJupyError("no paired representation exists")

    if ipynb_model is None:
        print_json(
            {
                "paired_paths": [str(ipynb_path), str(py_path)],
                "source": "text",
                "would_write": [str(ipynb_path)],
                "roundtrip_ok": False,
                "differences": [],
                "missing": missing,
                "errors": [],
            }
        )
        return
    if text_model is None:
        print_json(
            {
                "paired_paths": [str(ipynb_path), str(py_path)],
                "source": "ipynb",
                "would_write": [str(py_path)],
                "roundtrip_ok": False,
                "differences": [],
                "missing": missing,
                "errors": [],
            }
        )
        return

    ipynb_version = get_version(ipynb_model)
    text_version = get_version(text_model)
    if ipynb_version > text_version:
        source = "ipynb"
        would_write = [str(py_path)]
    elif text_version > ipynb_version:
        source = "text"
        would_write = [str(ipynb_path)]
    else:
        source = "none"
        would_write = []

    roundtrip_ok, differences = compare_text_representable(ipynb_model, text_model)
    print_json(
        {
            "paired_paths": [str(ipynb_path), str(py_path)],
            "source": source,
            "would_write": would_write,
            "roundtrip_ok": roundtrip_ok,
            "differences": differences,
            "missing": missing,
            "errors": [],
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minijupy.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--input", required=True)
    inspect_parser.add_argument("--config")
    inspect_parser.set_defaults(func=command_inspect)

    to_text_parser = subparsers.add_parser("to-text")
    to_text_parser.add_argument("--input", required=True)
    to_text_parser.add_argument("--output", required=True)
    to_text_parser.set_defaults(func=command_to_text)

    to_ipynb_parser = subparsers.add_parser("to-ipynb")
    to_ipynb_parser.add_argument("--input", required=True)
    to_ipynb_parser.add_argument("--output", required=True)
    to_ipynb_parser.set_defaults(func=command_to_ipynb)

    pair_parser = subparsers.add_parser("pair")
    pair_parser.add_argument("--input", required=True)
    pair_parser.add_argument("--formats", required=True)
    pair_parser.add_argument("--config")
    pair_parser.set_defaults(func=command_pair)

    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--input", required=True)
    sync_parser.add_argument("--config")
    sync_parser.add_argument("--source", choices=["ipynb", "text"])
    sync_parser.set_defaults(func=command_sync)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--input", required=True)
    status_parser.add_argument("--config")
    status_parser.set_defaults(func=command_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except MiniJupyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

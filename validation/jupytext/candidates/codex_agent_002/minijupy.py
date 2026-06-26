#!/usr/bin/env python3
import argparse
import ast
import copy
import json
import os
import sys
import tempfile
from pathlib import Path


SUPPORTED_FORMATS = "ipynb,py:percent"
SUPPORTED_NOTEBOOK_METADATA = ("minijupy", "kernelspec")
SUPPORTED_CELL_METADATA = ("tags", "name")


class MiniJupyError(Exception):
    pass


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def print_json(value):
    print(compact_json(value))


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise MiniJupyError(f"input file does not exist: {path}")
    except OSError as exc:
        raise MiniJupyError(f"could not read {path}: {exc}")


def read_json_file(path):
    text = read_text(path)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed .ipynb JSON: {exc.msg}")


def normalize_user_path(path):
    return Path(path).as_posix()


def user_path_to_abs(path, cwd):
    path = Path(path)
    if path.is_absolute():
        return path
    return cwd / path


def display_from_abs(path, cwd, prefer_absolute=False):
    path = Path(path)
    if prefer_absolute:
        return path.as_posix()
    try:
        return path.relative_to(cwd).as_posix()
    except ValueError:
        return path.as_posix()


def validate_formats(formats):
    if formats != SUPPORTED_FORMATS:
        raise MiniJupyError(f"unsupported formats value: {formats}")
    return formats


def validate_version(version):
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise MiniJupyError("invalid minijupy version")
    return version


def parse_config_value(raw):
    raw = raw.strip()
    if not raw:
        raise MiniJupyError("invalid config value")
    if raw[0] in ("'", '"'):
        try:
            value = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            raise MiniJupyError(f"invalid config value: {raw}")
        if not isinstance(value, str):
            raise MiniJupyError(f"invalid config value: {raw}")
        return value
    return raw


def load_config(input_abs, config_arg, cwd):
    if config_arg:
        config_abs = user_path_to_abs(config_arg, cwd)
    else:
        config_abs = input_abs.parent / "minijupy.toml"

    config = {
        "formats": SUPPORTED_FORMATS,
        "notebook_dir": "",
        "script_dir": "",
        "base_dir": cwd,
        "path": config_abs,
    }
    if not config_abs.exists():
        validate_formats(config["formats"])
        return config

    config["base_dir"] = config_abs.parent
    for line_no, line in enumerate(read_text(config_abs).splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise MiniJupyError(f"invalid config line {line_no}")
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        value = parse_config_value(raw_value)
        if key not in ("formats", "notebook_dir", "script_dir"):
            continue
        config[key] = value

    validate_formats(config["formats"])
    if not isinstance(config["notebook_dir"], str) or not isinstance(config["script_dir"], str):
        raise MiniJupyError("invalid config value")
    return config


def input_format(path):
    suffix = Path(path).suffix
    if suffix == ".ipynb":
        return "ipynb"
    if suffix == ".py":
        return "text"
    raise MiniJupyError("input file must be .ipynb or .py")


def path_under(child, parent):
    try:
        return child.relative_to(parent)
    except ValueError:
        return None


def derive_pair_paths(input_arg, config, cwd):
    input_user = Path(input_arg)
    input_abs = user_path_to_abs(input_user, cwd).resolve(strict=False)
    fmt = input_format(input_user)
    mapping_active = bool(config["notebook_dir"] and config["script_dir"])
    prefer_absolute = input_user.is_absolute()

    if not mapping_active:
        if input_user.is_absolute():
            if fmt == "ipynb":
                nb_abs = input_abs
                py_abs = input_abs.with_suffix(".py")
                nb_display = nb_abs.as_posix()
                py_display = py_abs.as_posix()
            else:
                py_abs = input_abs
                nb_abs = input_abs.with_suffix(".ipynb")
                py_display = py_abs.as_posix()
                nb_display = nb_abs.as_posix()
        else:
            if fmt == "ipynb":
                nb_abs = input_abs
                py_abs = input_abs.with_suffix(".py")
                nb_display = normalize_user_path(input_user)
                py_display = normalize_user_path(input_user.with_suffix(".py"))
            else:
                py_abs = input_abs
                nb_abs = input_abs.with_suffix(".ipynb")
                py_display = normalize_user_path(input_user)
                nb_display = normalize_user_path(input_user.with_suffix(".ipynb"))
        return {
            "format": fmt,
            "ipynb_abs": nb_abs,
            "text_abs": py_abs,
            "ipynb_display": nb_display,
            "text_display": py_display,
        }

    base = Path(config["base_dir"]).resolve(strict=False)
    nb_root = (base / config["notebook_dir"]).resolve(strict=False)
    script_root = (base / config["script_dir"]).resolve(strict=False)

    if fmt == "ipynb":
        rel = path_under(input_abs, nb_root)
        if rel is None:
            raise MiniJupyError("input .ipynb is not under configured notebook_dir")
        nb_abs = input_abs
        py_abs = (script_root / rel).with_suffix(".py")
    else:
        rel = path_under(input_abs, script_root)
        if rel is None:
            raise MiniJupyError("input .py is not under configured script_dir")
        py_abs = input_abs
        nb_abs = (nb_root / rel).with_suffix(".ipynb")

    return {
        "format": fmt,
        "ipynb_abs": nb_abs,
        "text_abs": py_abs,
        "ipynb_display": display_from_abs(nb_abs, cwd, prefer_absolute),
        "text_display": display_from_abs(py_abs, cwd, prefer_absolute),
    }


def supported_notebook_metadata(metadata, warnings):
    result = {}
    if not isinstance(metadata, dict):
        return result
    for key, value in metadata.items():
        if key == "minijupy":
            if isinstance(value, dict):
                cleaned = {}
                if "formats" in value:
                    cleaned["formats"] = validate_formats(value["formats"])
                if "version" in value:
                    cleaned["version"] = validate_version(value["version"])
                result["minijupy"] = cleaned
            else:
                raise MiniJupyError("invalid metadata.minijupy")
        elif key == "kernelspec":
            if isinstance(value, dict):
                result["kernelspec"] = value
            else:
                raise MiniJupyError("invalid metadata.kernelspec")
        else:
            warnings.append(f"unsupported-notebook-metadata:{key}")
    return result


def normalize_source(source):
    if isinstance(source, str):
        return source
    if isinstance(source, list) and all(isinstance(part, str) for part in source):
        return "".join(source)
    raise MiniJupyError("cell source must be a string")


def normalize_cell_metadata(metadata, cell_id, warnings):
    result = {}
    if not isinstance(metadata, dict):
        return result
    for key, value in metadata.items():
        if key == "tags":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise MiniJupyError("cell metadata.tags must be an array of strings")
            result["tags"] = value
        elif key == "name":
            if not isinstance(value, str):
                raise MiniJupyError("cell metadata.name must be a string")
            result["name"] = value
        else:
            warnings.append(f"unsupported-cell-metadata:{cell_id}:{key}")
    return result


def normalize_ipynb_object(raw):
    warnings = []
    if not isinstance(raw, dict):
        raise MiniJupyError("notebook must be a JSON object")
    metadata = supported_notebook_metadata(raw.get("metadata", {}), warnings)
    raw_cells = raw.get("cells", [])
    if not isinstance(raw_cells, list):
        raise MiniJupyError("notebook cells must be an array")

    cells = []
    seen = set()
    for index, raw_cell in enumerate(raw_cells, 1):
        if not isinstance(raw_cell, dict):
            raise MiniJupyError("cell must be an object")
        cell_id = raw_cell.get("id")
        generated_id = False
        if cell_id is None:
            cell_id = f"c{index}"
            generated_id = True
        if not isinstance(cell_id, str) or not cell_id:
            raise MiniJupyError("cell id must be a non-empty string")
        if cell_id in seen:
            raise MiniJupyError(f"duplicate cell id: {cell_id}")
        seen.add(cell_id)

        cell_type = raw_cell.get("cell_type", "code")
        if cell_type not in ("code", "markdown", "raw"):
            raise MiniJupyError(f"unsupported cell_type: {cell_type}")
        source = normalize_source(raw_cell.get("source", ""))
        cell_metadata = normalize_cell_metadata(raw_cell.get("metadata", {}), cell_id, warnings)

        if cell_type == "code":
            execution_count = raw_cell.get("execution_count")
            outputs = raw_cell.get("outputs", [])
            if outputs is None:
                outputs = []
            if not isinstance(outputs, list):
                raise MiniJupyError("cell outputs must be an array")
        else:
            execution_count = None
            outputs = []

        cells.append({
            "id": cell_id,
            "cell_type": cell_type,
            "source": source,
            "metadata": cell_metadata,
            "execution_count": execution_count,
            "outputs": outputs,
            "_generated_id": generated_id,
        })
    return {"metadata": metadata, "cells": cells, "warnings": warnings}


def parse_ipynb(path):
    return normalize_ipynb_object(read_json_file(path))


def parse_header_json(key, raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed JSON for header {key}: {exc.msg}")


def parse_marker_json(raw, line_no):
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed cell metadata JSON on line {line_no}: {exc.msg}")
    if not isinstance(value, dict):
        raise MiniJupyError(f"cell metadata on line {line_no} must be a JSON object")
    return value


def is_marker_candidate(line):
    return line.startswith("# %%")


def parse_marker(line, line_no, warnings):
    marker_type = "code"
    raw_json = None

    if line == "# %%":
        pass
    elif line.startswith("# %% [markdown]"):
        marker_type = "markdown"
        tail = line[len("# %% [markdown]"):]
        if tail:
            if not tail.startswith(" ") or tail == " ":
                raise MiniJupyError(f"malformed cell marker on line {line_no}")
            raw_json = tail[1:]
    elif line.startswith("# %% [raw]"):
        marker_type = "raw"
        tail = line[len("# %% [raw]"):]
        if tail:
            if not tail.startswith(" ") or tail == " ":
                raise MiniJupyError(f"malformed cell marker on line {line_no}")
            raw_json = tail[1:]
    elif line.startswith("# %% "):
        raw_json = line[len("# %% "):]
        if not raw_json:
            raise MiniJupyError(f"malformed cell marker on line {line_no}")
    else:
        raise MiniJupyError(f"malformed cell marker on line {line_no}")

    metadata = {}
    cell_id = None
    if raw_json is not None:
        marker = parse_marker_json(raw_json, line_no)
        for key, value in marker.items():
            if key == "id":
                if not isinstance(value, str) or not value:
                    raise MiniJupyError(f"invalid cell id on line {line_no}")
                cell_id = value
            elif key == "tags":
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    raise MiniJupyError(f"invalid tags on line {line_no}")
                metadata["tags"] = value
            elif key == "name":
                if not isinstance(value, str):
                    raise MiniJupyError(f"invalid name on line {line_no}")
                metadata["name"] = value
            else:
                warnings.append(f"unsupported-marker-field:{key}")
    return marker_type, cell_id, metadata


def parse_percent_text(text):
    warnings = []
    lines = text.splitlines()
    index = 0
    metadata = {}

    if lines and lines[0] == "# ---":
        index = 1
        while index < len(lines) and lines[index] != "# ---":
            line = lines[index]
            if not line.startswith("# ") or ": " not in line[2:]:
                raise MiniJupyError(f"malformed header line {index + 1}")
            key, raw = line[2:].split(": ", 1)
            if key == "minijupy":
                value = parse_header_json(key, raw)
                if not isinstance(value, dict):
                    raise MiniJupyError("metadata.minijupy must be an object")
                cleaned = {}
                if "formats" in value:
                    cleaned["formats"] = validate_formats(value["formats"])
                if "version" in value:
                    cleaned["version"] = validate_version(value["version"])
                metadata["minijupy"] = cleaned
            elif key == "kernelspec":
                value = parse_header_json(key, raw)
                if not isinstance(value, dict):
                    raise MiniJupyError("metadata.kernelspec must be an object")
                metadata["kernelspec"] = value
            else:
                warnings.append(f"unsupported-header:{key}")
            index += 1
        if index >= len(lines) or lines[index] != "# ---":
            raise MiniJupyError("malformed header block")
        index += 1

    while index < len(lines) and lines[index] == "":
        index += 1

    cells = []
    seen = set()
    while index < len(lines):
        if not is_marker_candidate(lines[index]):
            raise MiniJupyError(f"expected cell marker on line {index + 1}")
        cell_type, cell_id, cell_metadata = parse_marker(lines[index], index + 1, warnings)
        cell_index = len(cells) + 1
        generated_id = False
        if cell_id is None:
            cell_id = f"c{cell_index}"
            generated_id = True
        if cell_id in seen:
            raise MiniJupyError(f"duplicate cell id: {cell_id}")
        seen.add(cell_id)
        index += 1

        body = []
        while index < len(lines) and not is_marker_candidate(lines[index]):
            body.append(lines[index])
            index += 1
        if index < len(lines) and body and body[-1] == "":
            body = body[:-1]

        if cell_type == "code":
            source = "\n".join(body)
        else:
            unprefixed = []
            for line in body:
                if line == "#":
                    unprefixed.append("")
                elif line.startswith("# "):
                    unprefixed.append(line[2:])
                else:
                    raise MiniJupyError("malformed markdown/raw cell body")
            source = "\n".join(unprefixed)

        cells.append({
            "id": cell_id,
            "cell_type": cell_type,
            "source": source,
            "metadata": cell_metadata,
            "execution_count": None,
            "outputs": [],
            "_generated_id": generated_id,
        })

    return {"metadata": metadata, "cells": cells, "warnings": warnings}


def parse_text(path):
    return parse_percent_text(read_text(path))


def public_metadata(metadata):
    result = {}
    if "minijupy" in metadata:
        result["minijupy"] = copy.deepcopy(metadata["minijupy"])
    if "kernelspec" in metadata:
        result["kernelspec"] = copy.deepcopy(metadata["kernelspec"])
    return result


def public_cell(cell, include_outputs=True):
    result = {
        "id": cell["id"],
        "cell_type": cell["cell_type"],
        "source": cell["source"],
        "metadata": copy.deepcopy(cell["metadata"]),
        "execution_count": cell["execution_count"] if cell["cell_type"] == "code" else None,
    }
    if include_outputs:
        result["outputs"] = copy.deepcopy(cell["outputs"]) if cell["cell_type"] == "code" else []
    return result


def render_ipynb(model):
    notebook = {
        "metadata": public_metadata(model.get("metadata", {})),
        "cells": [public_cell(cell, include_outputs=True) for cell in model.get("cells", [])],
    }
    return compact_json(notebook) + "\n"


def split_source_lines(source):
    if source == "":
        return []
    return source.split("\n")


def render_text(model):
    lines = []
    metadata = public_metadata(model.get("metadata", {}))
    if any(key in metadata for key in SUPPORTED_NOTEBOOK_METADATA):
        lines.append("# ---")
        if "minijupy" in metadata:
            lines.append(f"# minijupy: {compact_json(metadata['minijupy'])}")
        if "kernelspec" in metadata:
            lines.append(f"# kernelspec: {compact_json(metadata['kernelspec'])}")
        lines.append("# ---")

    cells = model.get("cells", [])
    for index, cell in enumerate(cells):
        if lines:
            if lines[-1] != "":
                pass
        marker = "# %%"
        if cell["cell_type"] == "markdown":
            marker = "# %% [markdown]"
        elif cell["cell_type"] == "raw":
            marker = "# %% [raw]"
        marker_fields = {"id": cell["id"]}
        metadata = cell.get("metadata", {})
        if "tags" in metadata:
            marker_fields["tags"] = metadata["tags"]
        if "name" in metadata:
            marker_fields["name"] = metadata["name"]
        lines.append(f"{marker} {compact_json(marker_fields)}")

        if cell["cell_type"] == "code":
            lines.extend(split_source_lines(cell["source"]))
        else:
            for source_line in split_source_lines(cell["source"]):
                lines.append("#" if source_line == "" else f"# {source_line}")
        if index != len(cells) - 1:
            lines.append("")

    return "\n".join(lines) + ("\n" if lines else "")


def model_version(model):
    metadata = model.get("metadata", {})
    minijupy = metadata.get("minijupy", {})
    if not isinstance(minijupy, dict) or "version" not in minijupy:
        return 0
    return validate_version(minijupy["version"])


def model_formats(model, config):
    metadata = model.get("metadata", {})
    minijupy = metadata.get("minijupy", {})
    if isinstance(minijupy, dict) and "formats" in minijupy:
        return validate_formats(minijupy["formats"])
    return validate_formats(config["formats"])


def with_minijupy(model, formats, version):
    updated = copy.deepcopy(model)
    metadata = public_metadata(updated.get("metadata", {}))
    metadata["minijupy"] = {"formats": validate_formats(formats), "version": validate_version(version)}
    updated["metadata"] = metadata
    return updated


def inspect_cells(model):
    cells = []
    for cell in model["cells"]:
        cells.append({
            "id": cell["id"],
            "cell_type": cell["cell_type"],
            "source": cell["source"],
            "metadata": copy.deepcopy(cell["metadata"]),
            "execution_count": cell["execution_count"] if cell["cell_type"] == "code" else None,
            "has_outputs": bool(cell["outputs"]) if cell["cell_type"] == "code" else False,
        })
    return cells


def text_compare_signature(model):
    return {
        "metadata": public_metadata(model.get("metadata", {})),
        "cells": [
            {
                "cell_type": cell["cell_type"],
                "source": cell["source"],
                "metadata": copy.deepcopy(cell["metadata"]),
            }
            for cell in model.get("cells", [])
        ],
    }


def compare_text_representable(left, right):
    differences = []
    if public_metadata(left.get("metadata", {})) != public_metadata(right.get("metadata", {})):
        differences.append("metadata")
    left_cells = left.get("cells", [])
    right_cells = right.get("cells", [])
    if len(left_cells) != len(right_cells):
        differences.append("cell-count")
        return differences

    left_ids = [cell["id"] for cell in left_cells]
    right_ids = [cell["id"] for cell in right_cells]
    if set(left_ids) == set(right_ids) and left_ids != right_ids:
        differences.append("cell-order")

    checks = [
        ("cell_type", "cell-type"),
        ("source", "cell-source"),
    ]
    for left_cell, right_cell in zip(left_cells, right_cells):
        for key, reason in checks:
            if left_cell[key] != right_cell[key] and reason not in differences:
                differences.append(reason)
        if left_cell["metadata"].get("tags") != right_cell["metadata"].get("tags") and "cell-tags" not in differences:
            differences.append("cell-tags")
        if left_cell["metadata"].get("name") != right_cell["metadata"].get("name") and "cell-name" not in differences:
            differences.append("cell-name")
    return differences


def preserve_ipynb_outputs_from_existing(new_model, existing_ipynb):
    if existing_ipynb is None:
        return new_model
    existing_by_id = {cell["id"]: cell for cell in existing_ipynb.get("cells", [])}
    existing_cells = existing_ipynb.get("cells", [])
    updated = copy.deepcopy(new_model)
    for index, cell in enumerate(updated.get("cells", [])):
        if cell["cell_type"] != "code":
            cell["execution_count"] = None
            cell["outputs"] = []
            continue
        existing = None
        if not cell.get("_generated_id") and cell["id"] in existing_by_id:
            existing = existing_by_id[cell["id"]]
        elif index < len(existing_cells):
            existing = existing_cells[index]
        if existing and existing.get("cell_type") == "code":
            cell["execution_count"] = existing.get("execution_count")
            cell["outputs"] = copy.deepcopy(existing.get("outputs", []))
        else:
            cell["execution_count"] = None
            cell["outputs"] = []
    return updated


def prepare_temp_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
        return Path(temp_name)
    except Exception:
        try:
            os.unlink(temp_name)
        finally:
            raise


def write_many_atomically(writes):
    if not writes:
        return
    backups = {}
    temp_paths = {}
    replaced = []
    try:
        for path, data in writes.items():
            if path.exists():
                backups[path] = path.read_bytes()
            else:
                backups[path] = None
            temp_paths[path] = prepare_temp_file(path, data)
        for path, temp_path in temp_paths.items():
            os.replace(temp_path, path)
            replaced.append(path)
    except Exception as exc:
        for temp_path in temp_paths.values():
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
        for path in reversed(replaced):
            try:
                if backups[path] is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.write_bytes(backups[path])
            except OSError:
                pass
        if isinstance(exc, MiniJupyError):
            raise
        raise MiniJupyError(f"could not write output: {exc}")


def require_exists(path):
    if not path.exists():
        raise MiniJupyError(f"input file does not exist: {path}")


def parse_existing(path, fmt):
    if fmt == "ipynb":
        return parse_ipynb(path)
    return parse_text(path)


def command_to_text(args, cwd):
    if Path(args.input).suffix != ".ipynb":
        raise MiniJupyError("to-text input must be .ipynb")
    input_abs = user_path_to_abs(args.input, cwd)
    output_abs = user_path_to_abs(args.output, cwd)
    require_exists(input_abs)
    model = parse_ipynb(input_abs)
    write_many_atomically({output_abs: render_text(model)})
    print_json({"written": normalize_user_path(args.output), "cells": len(model["cells"])})


def command_to_ipynb(args, cwd):
    if Path(args.input).suffix != ".py":
        raise MiniJupyError("to-ipynb input must be .py")
    input_abs = user_path_to_abs(args.input, cwd)
    output_abs = user_path_to_abs(args.output, cwd)
    require_exists(input_abs)
    model = parse_text(input_abs)
    write_many_atomically({output_abs: render_ipynb(model)})
    print_json({"written": normalize_user_path(args.output), "cells": len(model["cells"])})


def command_inspect(args, cwd):
    input_abs = user_path_to_abs(args.input, cwd)
    require_exists(input_abs)
    config = load_config(input_abs, args.config, cwd)
    pairs = derive_pair_paths(args.input, config, cwd)
    model = parse_existing(input_abs, pairs["format"])
    formats = model_formats(model, config)
    result = {
        "input": normalize_user_path(args.input),
        "format": pairs["format"],
        "paired_paths": [pairs["ipynb_display"], pairs["text_display"]],
        "version": model_version(model),
        "formats": formats,
        "cells": inspect_cells(model),
        "warnings": model["warnings"],
    }
    print_json(result)


def command_pair(args, cwd):
    if Path(args.input).suffix != ".ipynb":
        raise MiniJupyError("pair input must be .ipynb")
    formats = validate_formats(args.formats)
    input_abs = user_path_to_abs(args.input, cwd)
    require_exists(input_abs)
    config = load_config(input_abs, args.config, cwd)
    pairs = derive_pair_paths(args.input, config, cwd)
    model = parse_ipynb(input_abs)
    version = model_version(model)
    paired_model = with_minijupy(model, formats, version)
    writes = {
        pairs["ipynb_abs"]: render_ipynb(paired_model),
        pairs["text_abs"]: render_text(paired_model),
    }
    write_many_atomically(writes)
    print_json({"paired_paths": [pairs["ipynb_display"], pairs["text_display"]], "version": version})


def determine_sync_source(nb_exists, text_exists, nb_model, text_model, source_arg):
    if source_arg:
        if source_arg not in ("ipynb", "text"):
            raise MiniJupyError(f"invalid source value: {source_arg}")
        if source_arg == "ipynb" and not nb_exists:
            raise MiniJupyError("source .ipynb file does not exist")
        if source_arg == "text" and not text_exists:
            raise MiniJupyError("source text file does not exist")
        return source_arg
    if nb_exists and not text_exists:
        return "ipynb"
    if text_exists and not nb_exists:
        return "text"
    nb_version = model_version(nb_model)
    text_version = model_version(text_model)
    if nb_version > text_version:
        return "ipynb"
    if text_version > nb_version:
        return "text"
    return "none"


def command_sync(args, cwd):
    input_abs = user_path_to_abs(args.input, cwd)
    require_exists(input_abs)
    config = load_config(input_abs, args.config, cwd)
    pairs = derive_pair_paths(args.input, config, cwd)
    nb_exists = pairs["ipynb_abs"].exists()
    text_exists = pairs["text_abs"].exists()

    nb_model = parse_ipynb(pairs["ipynb_abs"]) if nb_exists else None
    text_model = parse_text(pairs["text_abs"]) if text_exists else None
    source = determine_sync_source(nb_exists, text_exists, nb_model, text_model, args.source)

    if source == "none":
        version = model_version(nb_model)
        print_json({"source": "none", "wrote": [], "version": version, "synced": True})
        return

    if source == "ipynb":
        source_model = nb_model
        target_path = pairs["text_abs"]
        target_display = pairs["text_display"]
        target_data = render_text(with_minijupy(source_model, model_formats(source_model, config), model_version(source_model)))
    else:
        source_model = text_model
        target_path = pairs["ipynb_abs"]
        target_display = pairs["ipynb_display"]
        next_model = with_minijupy(source_model, model_formats(source_model, config), model_version(source_model))
        next_model = preserve_ipynb_outputs_from_existing(next_model, nb_model)
        target_data = render_ipynb(next_model)

    version = model_version(source_model)
    write_many_atomically({target_path: target_data})
    print_json({"source": source, "wrote": [target_display], "version": version, "synced": True})


def command_status(args, cwd):
    input_abs = user_path_to_abs(args.input, cwd)
    require_exists(input_abs)
    config = load_config(input_abs, args.config, cwd)
    pairs = derive_pair_paths(args.input, config, cwd)
    nb_exists = pairs["ipynb_abs"].exists()
    text_exists = pairs["text_abs"].exists()

    missing = []
    if not nb_exists:
        missing.append(pairs["ipynb_display"])
    if not text_exists:
        missing.append(pairs["text_display"])

    nb_model = parse_ipynb(pairs["ipynb_abs"]) if nb_exists else None
    text_model = parse_text(pairs["text_abs"]) if text_exists else None
    source = determine_sync_source(nb_exists, text_exists, nb_model, text_model, None)

    would_write = []
    if source == "ipynb":
        would_write = [pairs["text_display"]]
    elif source == "text":
        would_write = [pairs["ipynb_display"]]

    if not nb_exists or not text_exists:
        roundtrip_ok = False
        differences = []
    else:
        differences = compare_text_representable(nb_model, text_model)
        roundtrip_ok = not differences

    result = {
        "paired_paths": [pairs["ipynb_display"], pairs["text_display"]],
        "source": source,
        "would_write": would_write,
        "roundtrip_ok": roundtrip_ok,
        "differences": differences,
        "missing": missing,
        "errors": [],
    }
    print_json(result)


def build_parser():
    parser = argparse.ArgumentParser(prog="minijupy.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--input", required=True)
    inspect.add_argument("--config")

    to_text = subparsers.add_parser("to-text")
    to_text.add_argument("--input", required=True)
    to_text.add_argument("--output", required=True)

    to_ipynb = subparsers.add_parser("to-ipynb")
    to_ipynb.add_argument("--input", required=True)
    to_ipynb.add_argument("--output", required=True)

    pair = subparsers.add_parser("pair")
    pair.add_argument("--input", required=True)
    pair.add_argument("--formats", required=True)
    pair.add_argument("--config")

    sync = subparsers.add_parser("sync")
    sync.add_argument("--input", required=True)
    sync.add_argument("--config")
    sync.add_argument("--source")

    status = subparsers.add_parser("status")
    status.add_argument("--input", required=True)
    status.add_argument("--config")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    cwd = Path.cwd().resolve(strict=False)
    try:
        if args.command == "inspect":
            command_inspect(args, cwd)
        elif args.command == "to-text":
            command_to_text(args, cwd)
        elif args.command == "to-ipynb":
            command_to_ipynb(args, cwd)
        elif args.command == "pair":
            command_pair(args, cwd)
        elif args.command == "sync":
            command_sync(args, cwd)
        elif args.command == "status":
            command_status(args, cwd)
        else:
            raise MiniJupyError(f"unsupported command: {args.command}")
    except MiniJupyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

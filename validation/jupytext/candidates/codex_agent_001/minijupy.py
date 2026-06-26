#!/usr/bin/env python3
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


SUPPORTED_FORMATS = "ipynb,py:percent"


class MiniError(Exception):
    pass


class ParsedNotebook:
    def __init__(self, model, warnings=None, explicit_ids=None):
        self.model = model
        self.warnings = warnings or []
        self.explicit_ids = explicit_ids


def compact(obj):
    return json.dumps(obj, separators=(",", ":"))


def fail(message):
    print(message, file=sys.stderr)
    return 1


def path_text(path):
    return str(path)


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise MiniError(f"input file does not exist: {path}")
    except OSError as exc:
        raise MiniError(f"cannot read {path}: {exc}")


def parse_json_file(path):
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise MiniError(f"malformed .ipynb JSON: {exc.msg}")


def validate_formats(formats):
    if formats != SUPPORTED_FORMATS:
        raise MiniError(f"unsupported formats value: {formats}")


def validate_version(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MiniError("metadata.minijupy.version must be a non-negative integer")
    return value


def clean_notebook_metadata(raw, warnings):
    out = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if key == "minijupy":
            if not isinstance(value, dict):
                raise MiniError("metadata.minijupy must be an object")
            clean = {}
            if "formats" in value:
                if not isinstance(value["formats"], str):
                    raise MiniError("metadata.minijupy.formats must be a string")
                validate_formats(value["formats"])
                clean["formats"] = value["formats"]
            if "version" in value:
                clean["version"] = validate_version(value["version"])
            for extra in value:
                if extra not in {"formats", "version"}:
                    warnings.append(f"unsupported-minijupy-metadata:{extra}")
            out["minijupy"] = clean
        elif key == "kernelspec":
            out["kernelspec"] = value
        else:
            warnings.append(f"unsupported-notebook-metadata:{key}")
    return out


def clean_cell_metadata(raw, warnings):
    out = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if key == "tags":
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise MiniError("cell metadata tags must be an array of strings")
            out["tags"] = list(value)
        elif key == "name":
            if not isinstance(value, str):
                raise MiniError("cell metadata name must be a string")
            out["name"] = value
        else:
            warnings.append(f"unsupported-cell-metadata:{key}")
    return out


def normalize_cell(cell, index, warnings, id_value=None):
    if not isinstance(cell, dict):
        raise MiniError("notebook cell must be an object")
    cell_type = cell.get("cell_type")
    if cell_type not in {"code", "markdown", "raw"}:
        raise MiniError(f"unsupported cell_type: {cell_type}")
    if id_value is None:
        id_value = cell.get("id")
    if id_value is None:
        id_value = f"c{index}"
    if not isinstance(id_value, str):
        raise MiniError("cell id must be a string")
    source = cell.get("source", "")
    if isinstance(source, list):
        source = "".join(source)
    if not isinstance(source, str):
        raise MiniError("cell source must be a string")
    metadata = clean_cell_metadata(cell.get("metadata", {}), warnings)
    if cell_type == "code":
        execution_count = cell.get("execution_count")
        outputs = cell.get("outputs", [])
        if outputs is None:
            outputs = []
        if not isinstance(outputs, list):
            raise MiniError("code cell outputs must be an array")
    else:
        execution_count = None
        outputs = []
    return {
        "id": id_value,
        "cell_type": cell_type,
        "source": source,
        "metadata": metadata,
        "execution_count": execution_count,
        "outputs": outputs,
    }


def normalize_ipynb(obj):
    warnings = []
    if not isinstance(obj, dict):
        raise MiniError("notebook JSON must be an object")
    metadata = clean_notebook_metadata(obj.get("metadata", {}), warnings)
    raw_cells = obj.get("cells", [])
    if not isinstance(raw_cells, list):
        raise MiniError("notebook cells must be an array")
    cells = []
    seen = set()
    for index, raw in enumerate(raw_cells, start=1):
        cell = normalize_cell(raw, index, warnings)
        if cell["id"] in seen:
            raise MiniError(f"duplicate cell id: {cell['id']}")
        seen.add(cell["id"])
        cells.append(cell)
    return ParsedNotebook({"metadata": metadata, "cells": cells}, warnings)


def parse_ipynb(path):
    return normalize_ipynb(parse_json_file(path))


def split_source(source):
    if source == "":
        return []
    return source.split("\n")


def marker_kind_and_meta(line):
    if not line.startswith("# %%"):
        return None
    rest = line[4:]
    if rest == "":
        return "code", {}
    if not rest.startswith(" "):
        raise MiniError(f"malformed cell marker: {line}")
    rest = rest[1:]
    cell_type = "code"
    meta_text = rest
    if rest.startswith("[markdown]"):
        cell_type = "markdown"
        meta_text = rest[len("[markdown]") :]
    elif rest.startswith("[raw]"):
        cell_type = "raw"
        meta_text = rest[len("[raw]") :]
    if meta_text == "":
        return cell_type, {}
    if not meta_text.startswith(" "):
        if cell_type == "code":
            pass
        else:
            raise MiniError(f"malformed cell marker: {line}")
    elif cell_type != "code":
        meta_text = meta_text[1:]
    if cell_type == "code":
        meta_text = rest
    try:
        meta = json.loads(meta_text)
    except json.JSONDecodeError as exc:
        raise MiniError(f"malformed cell metadata JSON: {exc.msg}")
    if not isinstance(meta, dict):
        raise MiniError("cell marker metadata must be an object")
    return cell_type, meta


def is_marker(line):
    return line.startswith("# %%")


def parse_header(lines, warnings):
    metadata = {}
    if not lines or lines[0] != "# ---":
        return metadata, 0
    pos = 1
    while pos < len(lines) and lines[pos] != "# ---":
        line = lines[pos]
        if not line.startswith("# ") or ": " not in line[2:]:
            raise MiniError("malformed header block")
        key, raw_value = line[2:].split(": ", 1)
        if key in {"minijupy", "kernelspec"}:
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise MiniError(f"malformed header JSON for {key}: {exc.msg}")
            metadata[key] = value
        else:
            warnings.append(f"unsupported-header:{key}")
        pos += 1
    if pos >= len(lines):
        raise MiniError("bad header block: missing closing # ---")
    clean = clean_notebook_metadata(metadata, warnings)
    return clean, pos + 1


def marker_metadata_to_cell(marker_meta, warnings):
    cell = {"metadata": {}}
    explicit_id = None
    for key, value in marker_meta.items():
        if key == "id":
            if not isinstance(value, str):
                raise MiniError("cell marker id must be a string")
            explicit_id = value
        elif key == "tags":
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise MiniError("cell marker tags must be an array of strings")
            cell["metadata"]["tags"] = list(value)
        elif key == "name":
            if not isinstance(value, str):
                raise MiniError("cell marker name must be a string")
            cell["metadata"]["name"] = value
        else:
            warnings.append(f"unsupported-marker:{key}")
    return explicit_id, cell


def unprefix_comment_body(line):
    if line == "#":
        return ""
    if line.startswith("# "):
        return line[2:]
    return line


def parse_percent(path):
    warnings = []
    text = read_text(path)
    lines = text.splitlines()
    metadata, pos = parse_header(lines, warnings)
    cells = []
    seen = set()
    explicit_ids = []
    current = None
    current_body = []
    current_explicit_id = None

    def finish_cell(remove_separator):
        nonlocal current, current_body, current_explicit_id
        if current is None:
            return
        body = list(current_body)
        if remove_separator and body and body[-1] == "":
            body.pop()
        if current["cell_type"] in {"markdown", "raw"}:
            body = [unprefix_comment_body(line) for line in body]
        current["source"] = "\n".join(body)
        index = len(cells) + 1
        cell_id = current_explicit_id if current_explicit_id is not None else f"c{index}"
        current["id"] = cell_id
        if cell_id in seen:
            raise MiniError(f"duplicate cell id: {cell_id}")
        seen.add(cell_id)
        if current_explicit_id is not None:
            explicit_ids.append(cell_id)
        current["execution_count"] = None
        current["outputs"] = []
        cells.append(current)
        current = None
        current_body = []
        current_explicit_id = None

    while pos < len(lines):
        line = lines[pos]
        if is_marker(line):
            marker = marker_kind_and_meta(line)
            finish_cell(remove_separator=True)
            cell_type, marker_meta = marker
            explicit_id, base = marker_metadata_to_cell(marker_meta, warnings)
            current = {
                "id": None,
                "cell_type": cell_type,
                "source": "",
                "metadata": base["metadata"],
                "execution_count": None,
                "outputs": [],
            }
            current_body = []
            current_explicit_id = explicit_id
        else:
            if current is None:
                if line.strip() == "":
                    pass
                else:
                    raise MiniError("malformed percent script: content before first cell marker")
            else:
                current_body.append(line)
        pos += 1
    finish_cell(remove_separator=False)
    return ParsedNotebook({"metadata": metadata, "cells": cells}, warnings, explicit_ids)


def metadata_version(model):
    mini = model.get("metadata", {}).get("minijupy")
    if isinstance(mini, dict) and "version" in mini:
        return validate_version(mini["version"])
    return 0


def metadata_formats(model, default_formats=SUPPORTED_FORMATS):
    mini = model.get("metadata", {}).get("minijupy")
    if isinstance(mini, dict) and "formats" in mini:
        validate_formats(mini["formats"])
        return mini["formats"]
    validate_formats(default_formats)
    return default_formats


def with_minijupy(model, formats, version):
    validate_formats(formats)
    version = validate_version(version)
    metadata = {}
    if "kernelspec" in model.get("metadata", {}):
        metadata["kernelspec"] = model["metadata"]["kernelspec"]
    metadata["minijupy"] = {"formats": formats, "version": version}
    return {"metadata": metadata, "cells": clone_cells(model.get("cells", []))}


def clone_cells(cells):
    return [json.loads(compact(cell)) for cell in cells]


def notebook_for_write(model):
    return {
        "metadata": dict(model.get("metadata", {})),
        "cells": clone_cells(model.get("cells", [])),
    }


def serialize_ipynb(model):
    return compact(notebook_for_write(model)) + "\n"


def marker_for_cell(cell):
    cell_type = cell["cell_type"]
    if cell_type == "markdown":
        prefix = "# %% [markdown]"
    elif cell_type == "raw":
        prefix = "# %% [raw]"
    else:
        prefix = "# %%"
    meta = {"id": cell["id"]}
    if "tags" in cell.get("metadata", {}):
        meta["tags"] = cell["metadata"]["tags"]
    if "name" in cell.get("metadata", {}):
        meta["name"] = cell["metadata"]["name"]
    return f"{prefix} {compact(meta)}"


def serialize_percent(model):
    lines = []
    metadata = model.get("metadata", {})
    header_pairs = []
    if "minijupy" in metadata:
        header_pairs.append(("minijupy", metadata["minijupy"]))
    if "kernelspec" in metadata:
        header_pairs.append(("kernelspec", metadata["kernelspec"]))
    if header_pairs:
        lines.append("# ---")
        for key, value in header_pairs:
            lines.append(f"# {key}: {compact(value)}")
        lines.append("# ---")
    for index, cell in enumerate(model.get("cells", [])):
        if lines:
            lines.append("")
        lines.append(marker_for_cell(cell))
        if cell["cell_type"] in {"markdown", "raw"}:
            for source_line in split_source(cell.get("source", "")):
                lines.append("#" if source_line == "" else f"# {source_line}")
        else:
            for source_line in split_source(cell.get("source", "")):
                lines.append(source_line)
    return "\n".join(lines) + "\n"


def parse_value(raw):
    value = raw.strip()
    if value == "":
        raise MiniError("invalid config value")
    if value[0] in {'"', "'"}:
        try:
            return json.loads(value) if value[0] == '"' else value[1:-1]
        except json.JSONDecodeError:
            raise MiniError("invalid config value")
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def load_config(input_path, config_arg):
    if config_arg:
        config_path = Path(config_arg)
    else:
        config_path = Path(input_path).parent / "minijupy.toml"
    config = {
        "formats": SUPPORTED_FORMATS,
        "notebook_dir": "",
        "script_dir": "",
        "base": Path.cwd(),
    }
    if not config_path.exists():
        return config
    config["base"] = config_path.parent if str(config_path.parent) else Path(".")
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise MiniError(f"cannot read config: {exc}")
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise MiniError(f"invalid config line {lineno}")
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        value = parse_value(raw_value)
        if key not in {"formats", "notebook_dir", "script_dir"}:
            continue
        if not isinstance(value, str):
            raise MiniError(f"invalid config value for {key}")
        if "\x00" in value:
            raise MiniError(f"invalid config value for {key}")
        config[key] = value
    validate_formats(config["formats"])
    return config


def file_format(path):
    suffix = Path(path).suffix
    if suffix == ".ipynb":
        return "ipynb"
    if suffix == ".py":
        return "text"
    raise MiniError(f"unsupported input extension: {path}")


def ensure_under(path, root, label):
    abs_path = Path(path).resolve(strict=False)
    abs_root = Path(root).resolve(strict=False)
    try:
        return abs_path.relative_to(abs_root)
    except ValueError:
        raise MiniError(f"input path is not under configured {label}: {root}")


def paired_paths(input_path, formats, config):
    validate_formats(formats)
    path = Path(input_path)
    side = file_format(path)
    notebook_dir = config.get("notebook_dir", "")
    script_dir = config.get("script_dir", "")
    if notebook_dir and script_dir:
        base = config.get("base", Path.cwd())
        nb_root = Path(base) / notebook_dir
        py_root = Path(base) / script_dir
        if side == "ipynb":
            rel = ensure_under(path, nb_root, "notebook_dir")
            rel = rel.with_suffix(".py")
            return path, py_root / rel
        rel = ensure_under(path, py_root, "script_dir")
        rel = rel.with_suffix(".ipynb")
        return nb_root / rel, path
    if side == "ipynb":
        return path, path.with_suffix(".py")
    return path.with_suffix(".ipynb"), path


def atomic_write_many(contents):
    temp_paths = []
    backups = {}
    replaced = []
    try:
        for path, data in contents:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
            temp_path = Path(temp_name)
            temp_paths.append(temp_path)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(data)
        for (path, _data), temp_path in zip(contents, temp_paths):
            path = Path(path)
            if path.exists():
                backups[path] = path.read_bytes()
            else:
                backups[path] = None
            os.replace(temp_path, path)
            replaced.append(path)
        temp_paths.clear()
    except Exception:
        for path in reversed(replaced):
            backup = backups.get(path)
            try:
                if backup is None:
                    if path.exists():
                        path.unlink()
                elif backup is not None:
                    path.write_bytes(backup)
            except OSError:
                pass
        raise
    finally:
        for temp_path in temp_paths:
            try:
                temp_path.unlink()
            except OSError:
                pass


def inspect_cells(model):
    cells = []
    for cell in model.get("cells", []):
        cells.append({
            "id": cell["id"],
            "cell_type": cell["cell_type"],
            "source": cell["source"],
            "metadata": dict(cell.get("metadata", {})),
            "execution_count": cell["execution_count"] if cell["cell_type"] == "code" else None,
            "has_outputs": bool(cell.get("outputs")) if cell["cell_type"] == "code" else False,
        })
    return cells


def parse_by_path(path):
    fmt = file_format(path)
    if fmt == "ipynb":
        return parse_ipynb(path)
    return parse_percent(path)


def comparable_cells(model):
    result = []
    for cell in model.get("cells", []):
        result.append({
            "cell_type": cell["cell_type"],
            "source": cell["source"],
            "metadata": dict(cell.get("metadata", {})),
        })
    return result


def compare_models_for_text(ipynb_model, text_model):
    differences = []
    if ipynb_model.get("metadata", {}) != text_model.get("metadata", {}):
        differences.append("metadata")
    left = ipynb_model.get("cells", [])
    right = text_model.get("cells", [])
    if len(left) != len(right):
        differences.append("cell-count")
    left_ids = [cell["id"] for cell in left]
    right_ids = [cell["id"] for cell in right]
    compare_right = right
    if len(left) == len(right) and set(left_ids) == set(right_ids):
        if left_ids != right_ids:
            differences.append("cell-order")
        by_id = {cell["id"]: cell for cell in right}
        compare_right = [by_id[cell["id"]] for cell in left]
    for a, b in zip(left, compare_right):
        if a["cell_type"] != b["cell_type"]:
            differences.append("cell-type")
            break
    for a, b in zip(left, compare_right):
        if a["source"] != b["source"]:
            differences.append("cell-source")
            break
    for a, b in zip(left, compare_right):
        if a.get("metadata", {}).get("tags") != b.get("metadata", {}).get("tags"):
            differences.append("cell-tags")
            break
    for a, b in zip(left, compare_right):
        if a.get("metadata", {}).get("name") != b.get("metadata", {}).get("name"):
            differences.append("cell-name")
            break
    aligned_text_model = {"cells": compare_right}
    if not differences and comparable_cells(ipynb_model) != comparable_cells(aligned_text_model):
        differences.append("cell-model")
    seen = []
    for item in differences:
        if item not in seen:
            seen.append(item)
    return seen


def preserve_ipynb_outputs(source_model, existing_ipynb_model, use_ids):
    existing_cells = existing_ipynb_model.get("cells", []) if existing_ipynb_model else []
    by_id = {cell["id"]: cell for cell in existing_cells}
    new_cells = []
    for index, cell in enumerate(source_model.get("cells", [])):
        new_cell = json.loads(compact(cell))
        if new_cell["cell_type"] == "code":
            match = None
            if use_ids:
                match = by_id.get(new_cell["id"])
            elif index < len(existing_cells):
                match = existing_cells[index]
            if match and match.get("cell_type") == "code":
                new_cell["execution_count"] = match.get("execution_count")
                new_cell["outputs"] = match.get("outputs", [])
            else:
                new_cell["execution_count"] = None
                new_cell["outputs"] = []
        else:
            new_cell["execution_count"] = None
            new_cell["outputs"] = []
        new_cells.append(new_cell)
    return {"metadata": dict(source_model.get("metadata", {})), "cells": new_cells}


def command_inspect(args):
    input_path = Path(args.input)
    if not input_path.exists():
        raise MiniError(f"input file does not exist: {input_path}")
    config = load_config(input_path, args.config)
    parsed = parse_by_path(input_path)
    formats = metadata_formats(parsed.model, config["formats"])
    nb_path, py_path = paired_paths(input_path, formats, config)
    result = {
        "input": path_text(input_path),
        "format": file_format(input_path),
        "paired_paths": [path_text(nb_path), path_text(py_path)],
        "version": metadata_version(parsed.model),
        "formats": formats,
        "cells": inspect_cells(parsed.model),
        "warnings": parsed.warnings,
    }
    print(compact(result))


def command_to_text(args):
    input_path = Path(args.input)
    output_path = Path(args.output)
    if input_path.suffix != ".ipynb":
        raise MiniError("to-text input must be .ipynb")
    if not input_path.exists():
        raise MiniError(f"input file does not exist: {input_path}")
    parsed = parse_ipynb(input_path)
    data = serialize_percent(parsed.model)
    atomic_write_many([(output_path, data)])
    print(compact({"written": path_text(output_path), "cells": len(parsed.model["cells"])}))


def command_to_ipynb(args):
    input_path = Path(args.input)
    output_path = Path(args.output)
    if input_path.suffix != ".py":
        raise MiniError("to-ipynb input must be .py")
    if not input_path.exists():
        raise MiniError(f"input file does not exist: {input_path}")
    parsed = parse_percent(input_path)
    data = serialize_ipynb(parsed.model)
    atomic_write_many([(output_path, data)])
    print(compact({"written": path_text(output_path), "cells": len(parsed.model["cells"])}))


def command_pair(args):
    input_path = Path(args.input)
    if input_path.suffix != ".ipynb":
        raise MiniError("pair input must be .ipynb")
    if not input_path.exists():
        raise MiniError(f"input file does not exist: {input_path}")
    validate_formats(args.formats)
    config = load_config(input_path, args.config)
    parsed = parse_ipynb(input_path)
    version = metadata_version(parsed.model)
    paired_model = with_minijupy(parsed.model, args.formats, version)
    nb_path, py_path = paired_paths(input_path, args.formats, config)
    atomic_write_many([
        (nb_path, serialize_ipynb(paired_model)),
        (py_path, serialize_percent(paired_model)),
    ])
    print(compact({"paired_paths": [path_text(nb_path), path_text(py_path)], "version": version}))


def select_sync_source(nb_exists, py_exists, nb_model, py_model, forced):
    if forced:
        if forced == "ipynb":
            if not nb_exists:
                raise MiniError("forced ipynb source does not exist")
            return "ipynb"
        if forced == "text":
            if not py_exists:
                raise MiniError("forced text source does not exist")
            return "text"
        raise MiniError(f"invalid --source value: {forced}")
    if nb_exists and not py_exists:
        return "ipynb"
    if py_exists and not nb_exists:
        return "text"
    nb_version = metadata_version(nb_model)
    py_version = metadata_version(py_model)
    if nb_version > py_version:
        return "ipynb"
    if py_version > nb_version:
        return "text"
    return "none"


def command_sync(args):
    input_path = Path(args.input)
    if not input_path.exists():
        raise MiniError(f"input file does not exist: {input_path}")
    config = load_config(input_path, args.config)
    input_parsed = parse_by_path(input_path)
    formats = metadata_formats(input_parsed.model, config["formats"])
    nb_path, py_path = paired_paths(input_path, formats, config)
    nb_exists = nb_path.exists()
    py_exists = py_path.exists()
    nb_parsed = None
    py_parsed = None
    if args.source == "ipynb":
        if not nb_exists:
            raise MiniError("forced ipynb source does not exist")
        nb_parsed = parse_ipynb(nb_path)
        source = "ipynb"
    elif args.source == "text":
        if not py_exists:
            raise MiniError("forced text source does not exist")
        py_parsed = parse_percent(py_path)
        if nb_exists:
            try:
                nb_parsed = parse_ipynb(nb_path)
            except MiniError:
                nb_parsed = None
        source = "text"
    else:
        if nb_exists:
            nb_parsed = parse_ipynb(nb_path)
        if py_exists:
            py_parsed = parse_percent(py_path)
        source = select_sync_source(
            nb_exists,
            py_exists,
            nb_parsed.model if nb_parsed else None,
            py_parsed.model if py_parsed else None,
            None,
        )
    if source == "none":
        version = metadata_version(input_parsed.model)
        print(compact({"source": "none", "wrote": [], "version": version, "synced": True}))
        return
    if source == "ipynb":
        source_model = nb_parsed.model
        version = metadata_version(source_model)
        source_model = with_minijupy(source_model, formats, version)
        target_model = source_model
        writes = [(py_path, serialize_percent(target_model))]
        wrote = [path_text(py_path)]
    else:
        source_model = py_parsed.model
        version = metadata_version(source_model)
        source_model = with_minijupy(source_model, formats, version)
        existing_ipynb = nb_parsed.model if nb_parsed else None
        use_ids = bool(py_parsed.explicit_ids)
        target_model = preserve_ipynb_outputs(source_model, existing_ipynb, use_ids)
        writes = [(nb_path, serialize_ipynb(target_model))]
        wrote = [path_text(nb_path)]
    atomic_write_many(writes)
    print(compact({"source": source, "wrote": wrote, "version": version, "synced": True}))


def command_status(args):
    input_path = Path(args.input)
    if not input_path.exists():
        raise MiniError(f"input file does not exist: {input_path}")
    config = load_config(input_path, args.config)
    input_parsed = parse_by_path(input_path)
    formats = metadata_formats(input_parsed.model, config["formats"])
    nb_path, py_path = paired_paths(input_path, formats, config)
    nb_exists = nb_path.exists()
    py_exists = py_path.exists()
    missing = []
    errors = []
    nb_parsed = None
    py_parsed = None
    if nb_exists:
        try:
            nb_parsed = parse_ipynb(nb_path)
        except MiniError as exc:
            errors.append(path_text(nb_path) + ": " + str(exc))
    else:
        missing.append(path_text(nb_path))
    if py_exists:
        try:
            py_parsed = parse_percent(py_path)
        except MiniError as exc:
            errors.append(path_text(py_path) + ": " + str(exc))
    else:
        missing.append(path_text(py_path))
    source = "none"
    would_write = []
    differences = []
    roundtrip_ok = False
    if errors:
        roundtrip_ok = False
    elif nb_exists and not py_exists:
        source = "ipynb"
        would_write = [path_text(py_path)]
    elif py_exists and not nb_exists:
        source = "text"
        would_write = [path_text(nb_path)]
    elif nb_exists and py_exists:
        nb_version = metadata_version(nb_parsed.model)
        py_version = metadata_version(py_parsed.model)
        if nb_version > py_version:
            source = "ipynb"
            would_write = [path_text(py_path)]
        elif py_version > nb_version:
            source = "text"
            would_write = [path_text(nb_path)]
        differences = compare_models_for_text(nb_parsed.model, py_parsed.model)
        roundtrip_ok = not differences
    result = {
        "paired_paths": [path_text(nb_path), path_text(py_path)],
        "source": source,
        "would_write": would_write,
        "roundtrip_ok": roundtrip_ok,
        "differences": differences,
        "missing": missing,
        "errors": errors,
    }
    print(compact(result))


def build_parser():
    parser = argparse.ArgumentParser(prog="minijupy.py")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_p = sub.add_parser("inspect")
    inspect_p.add_argument("--input", required=True)
    inspect_p.add_argument("--config")
    inspect_p.set_defaults(func=command_inspect)

    to_text = sub.add_parser("to-text")
    to_text.add_argument("--input", required=True)
    to_text.add_argument("--output", required=True)
    to_text.set_defaults(func=command_to_text)

    to_ipynb = sub.add_parser("to-ipynb")
    to_ipynb.add_argument("--input", required=True)
    to_ipynb.add_argument("--output", required=True)
    to_ipynb.set_defaults(func=command_to_ipynb)

    pair_p = sub.add_parser("pair")
    pair_p.add_argument("--input", required=True)
    pair_p.add_argument("--formats", required=True)
    pair_p.add_argument("--config")
    pair_p.set_defaults(func=command_pair)

    sync_p = sub.add_parser("sync")
    sync_p.add_argument("--input", required=True)
    sync_p.add_argument("--config")
    sync_p.add_argument("--source", choices=["ipynb", "text"])
    sync_p.set_defaults(func=command_sync)

    status_p = sub.add_parser("status")
    status_p.add_argument("--input", required=True)
    status_p.add_argument("--config")
    status_p.set_defaults(func=command_status)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except MiniError as exc:
        return fail(str(exc))
    except OSError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())

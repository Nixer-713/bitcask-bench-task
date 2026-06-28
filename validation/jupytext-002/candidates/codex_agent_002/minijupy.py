#!/usr/bin/env python3
import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path


FORMATS = "ipynb,py:percent"
STATE_NAME = ".minijupy-state.json"


class MiniJupyError(Exception):
    pass


def fail(message):
    print(message, file=sys.stderr)
    return 1


def as_posix(path):
    return Path(path).as_posix()


def rel_to(path, root):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise MiniJupyError(f"path mismatch: {path}") from exc


def stable_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(model):
    return hashlib.sha256(stable_json(public_hash_model(model)).encode("utf-8")).hexdigest()


def public_hash_model(model):
    cloned = copy.deepcopy(model)
    return cloned


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MiniJupyError(f"cannot read {path}: {exc}") from exc


def read_json(path):
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed JSON notebook: {path}: {exc}") from exc


def atomic_write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(text)
        os.replace(tmp, path)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_json(path, value):
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def parse_config(config_arg):
    if config_arg is None:
        return {
            "path": None,
            "root": Path.cwd().resolve(),
            "formats": None,
            "notebook_dir": None,
            "script_dir": None,
            "mapped": False,
        }
    path = Path(config_arg).resolve()
    data = {}
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise MiniJupyError("invalid config")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in {"formats", "notebook_dir", "script_dir"}:
            raise MiniJupyError("invalid config")
        if len(value) < 2 or value[0] != '"' or value[-1] != '"':
            raise MiniJupyError("invalid config")
        data[key] = value[1:-1]
    if "formats" in data and data["formats"] not in {FORMATS, "py:percent,ipynb"}:
        raise MiniJupyError("invalid config")
    has_nb = "notebook_dir" in data
    has_py = "script_dir" in data
    if has_nb != has_py:
        raise MiniJupyError("invalid config")
    root = path.parent.resolve()
    return {
        "path": path,
        "root": root,
        "formats": data.get("formats"),
        "notebook_dir": data.get("notebook_dir"),
        "script_dir": data.get("script_dir"),
        "mapped": has_nb and has_py,
    }


def format_of(path):
    suffix = path.suffix.lower()
    if suffix == ".ipynb":
        return "ipynb"
    if suffix == ".py":
        return "text"
    raise MiniJupyError(f"unsupported file type: {path}")


def counterpart_for(path, config):
    path = Path(path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    root = config["root"]
    fmt = format_of(path)
    if config["mapped"]:
        nb_root = (root / config["notebook_dir"]).resolve()
        py_root = (root / config["script_dir"]).resolve()
        if fmt == "ipynb":
            try:
                inner = path.relative_to(nb_root)
            except ValueError as exc:
                raise MiniJupyError(f"path mismatch: {path}") from exc
            other = py_root / inner.with_suffix(".py")
            ipynb = path
            text = other
        else:
            try:
                inner = path.relative_to(py_root)
            except ValueError as exc:
                raise MiniJupyError(f"path mismatch: {path}") from exc
            other = nb_root / inner.with_suffix(".ipynb")
            ipynb = other
            text = path
    else:
        rel_to(path, root)
        if fmt == "ipynb":
            ipynb = path
            text = path.with_suffix(".py")
        else:
            ipynb = path.with_suffix(".ipynb")
            text = path
    return {
        "ipynb": ipynb.resolve(),
        "text": text.resolve(),
        "ipynb_rel": rel_to(ipynb, root),
        "text_rel": rel_to(text, root),
        "key": rel_to(ipynb, root),
    }


def validate_version(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MiniJupyError("invalid version")
    return value


def join_source(source):
    if source is None:
        return ""
    if isinstance(source, str):
        return source
    if isinstance(source, list) and all(isinstance(part, str) for part in source):
        return "".join(source)
    raise MiniJupyError("invalid source")


def clean_cell_metadata(metadata):
    if not isinstance(metadata, dict):
        metadata = {}
    cleaned = {}
    tags = metadata.get("tags")
    if isinstance(tags, list) and all(isinstance(tag, str) for tag in tags):
        cleaned["tags"] = list(tags)
    name = metadata.get("name")
    if isinstance(name, str):
        cleaned["name"] = name
    return cleaned


def normalize_notebook(raw, paired=False):
    if not isinstance(raw, dict):
        raise MiniJupyError("malformed JSON notebook")
    if raw.get("nbformat") != 4:
        raise MiniJupyError("unsupported notebook nbformat")
    metadata = raw.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    minijupy = metadata.get("minijupy") or {}
    if not isinstance(minijupy, dict):
        minijupy = {}
    version = validate_version(minijupy.get("version", 1))
    formats = minijupy.get("formats")
    out_minijupy = {"version": version}
    if paired:
        out_minijupy["formats"] = FORMATS
    elif isinstance(formats, str):
        out_minijupy["formats"] = formats
    elif formats is not None:
        raise MiniJupyError("invalid formats")

    cells = raw.get("cells") or []
    if not isinstance(cells, list):
        raise MiniJupyError("invalid cells")
    seen = set()
    normalized_cells = []
    for index, cell in enumerate(cells, start=1):
        if not isinstance(cell, dict):
            raise MiniJupyError("invalid cell")
        cell_type = cell.get("cell_type")
        if cell_type not in {"code", "markdown", "raw"}:
            raise MiniJupyError("unsupported cell type")
        cell_id = cell.get("id") or f"c{index}"
        if not isinstance(cell_id, str):
            raise MiniJupyError("invalid cell id")
        if cell_id in seen:
            raise MiniJupyError("duplicate cell ids")
        seen.add(cell_id)
        new_cell = {
            "id": cell_id,
            "cell_type": cell_type,
            "source": join_source(cell.get("source", "")),
            "metadata": clean_cell_metadata(cell.get("metadata") or {}),
        }
        if cell_type == "code":
            new_cell["execution_count"] = cell.get("execution_count")
            new_cell["outputs"] = cell.get("outputs") if isinstance(cell.get("outputs"), list) else []
        normalized_cells.append(new_cell)
    return {
        "nbformat": 4,
        "nbformat_minor": raw.get("nbformat_minor", 5),
        "metadata": {
            "kernelspec": metadata.get("kernelspec") if isinstance(metadata.get("kernelspec"), dict) else {},
            "language_info": metadata.get("language_info") if isinstance(metadata.get("language_info"), dict) else {},
            "minijupy": out_minijupy,
        },
        "cells": normalized_cells,
    }


def parse_header(lines):
    meta = {"minijupy": {}, "kernelspec": {}}
    if not lines or lines[0].rstrip("\n") != "# ---":
        return meta, 0
    section = None
    index = 1
    while index < len(lines):
        raw = lines[index].rstrip("\n")
        index += 1
        if raw == "# ---":
            return meta, index
        if raw.startswith("# "):
            content = raw[2:]
        elif raw == "#":
            content = ""
        else:
            continue
        if not content:
            continue
        if not content.startswith(" ") and content.endswith(":"):
            section = content[:-1].strip()
            continue
        if section in {"minijupy", "kernelspec"} and content.startswith("  ") and ":" in content:
            key, value = content.strip().split(":", 1)
            value = value.strip()
            if section == "minijupy" and key == "version":
                try:
                    meta["minijupy"]["version"] = int(value)
                except ValueError as exc:
                    raise MiniJupyError("invalid version") from exc
            elif section == "minijupy" and key == "formats":
                meta["minijupy"]["formats"] = value
            elif section == "kernelspec" and key == "name":
                meta["kernelspec"]["name"] = value
    return {"minijupy": {}, "kernelspec": {}}, 0


MARKER_RE = re.compile(r"^# %%(?:\s+\[(markdown|md|raw)\])?(?:\s+(\{.*\}))?\s*$")


def parse_marker(line):
    match = MARKER_RE.match(line.rstrip("\n"))
    if not match:
        raise MiniJupyError("malformed percent marker")
    kind = match.group(1)
    cell_type = "code"
    if kind in {"markdown", "md"}:
        cell_type = "markdown"
    elif kind == "raw":
        cell_type = "raw"
    marker_meta = {}
    if match.group(2):
        try:
            marker_meta = json.loads(match.group(2))
        except json.JSONDecodeError as exc:
            raise MiniJupyError("malformed percent marker JSON") from exc
        if not isinstance(marker_meta, dict):
            raise MiniJupyError("malformed percent marker JSON")
        marker_meta = {k: v for k, v in marker_meta.items() if k in {"id", "tags", "name"}}
    return cell_type, marker_meta


def decode_markdown(lines):
    out = []
    for line in lines:
        if line.startswith("# "):
            out.append(line[2:])
        else:
            out.append(line)
    return "".join(out)


def normalize_script_cells(cells, meta, paired=False):
    minijupy = meta.get("minijupy") or {}
    version = validate_version(minijupy.get("version", 1))
    formats = minijupy.get("formats")
    out_minijupy = {"version": version}
    if paired:
        out_minijupy["formats"] = FORMATS
    elif isinstance(formats, str):
        out_minijupy["formats"] = formats
    elif formats is not None:
        raise MiniJupyError("invalid formats")
    seen = set()
    out_cells = []
    for index, cell in enumerate(cells, start=1):
        marker_meta = cell.get("metadata") or {}
        cell_id = marker_meta.get("id") or f"c{index}"
        if not isinstance(cell_id, str):
            raise MiniJupyError("invalid cell id")
        if cell_id in seen:
            raise MiniJupyError("duplicate cell ids")
        seen.add(cell_id)
        cell_meta = clean_cell_metadata(marker_meta)
        new_cell = {
            "id": cell_id,
            "cell_type": cell["cell_type"],
            "source": cell["source"],
            "metadata": cell_meta,
        }
        if cell["cell_type"] == "code":
            new_cell["execution_count"] = None
            new_cell["outputs"] = []
        out_cells.append(new_cell)
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": meta.get("kernelspec") if isinstance(meta.get("kernelspec"), dict) else {},
            "language_info": {},
            "minijupy": out_minijupy,
        },
        "cells": out_cells,
    }


def parse_script(path, paired=False):
    lines = read_text(path).splitlines(keepends=True)
    meta, start = parse_header(lines)
    cells = []
    current = None
    body = []
    prefix = []
    for line in lines[start:]:
        if line.startswith("# %%"):
            cell_type, marker_meta = parse_marker(line)
            if current is not None:
                source = decode_markdown(body) if current["cell_type"] == "markdown" else "".join(body)
                cells.append({"cell_type": current["cell_type"], "metadata": current["metadata"], "source": source})
            elif any(piece.strip() for piece in prefix):
                cells.append({"cell_type": "code", "metadata": {}, "source": "".join(prefix)})
            prefix = []
            current = {"cell_type": cell_type, "metadata": marker_meta}
            body = []
        else:
            if current is None:
                prefix.append(line)
            else:
                body.append(line)
    if current is not None:
        source = decode_markdown(body) if current["cell_type"] == "markdown" else "".join(body)
        cells.append({"cell_type": current["cell_type"], "metadata": current["metadata"], "source": source})
    elif any(piece.strip() for piece in prefix):
        cells.append({"cell_type": "code", "metadata": {}, "source": "".join(prefix)})
    return normalize_script_cells(cells, meta, paired=paired)


def read_model(path, paired=False):
    fmt = format_of(path)
    if fmt == "ipynb":
        return normalize_notebook(read_json(path), paired=paired)
    return parse_script(path, paired=paired)


def model_version(model):
    return model["metadata"]["minijupy"]["version"]


def set_paired(model):
    copied = copy.deepcopy(model)
    copied["metadata"].setdefault("minijupy", {})["formats"] = FORMATS
    copied["metadata"]["minijupy"]["version"] = model_version(model)
    return copied


def marker_json(cell):
    data = {"id": cell["id"]}
    tags = cell.get("metadata", {}).get("tags")
    name = cell.get("metadata", {}).get("name")
    if tags is not None:
        data["tags"] = tags
    if name is not None:
        data["name"] = name
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def write_script_text(model):
    meta = model["metadata"]
    mini = meta.get("minijupy", {})
    lines = ["# ---\n", "# minijupy:\n"]
    if "formats" in mini:
        lines.append(f"#   formats: {mini['formats']}\n")
    lines.append(f"#   version: {model_version(model)}\n")
    name = meta.get("kernelspec", {}).get("name") if isinstance(meta.get("kernelspec"), dict) else None
    if name:
        lines.extend(["# kernelspec:\n", f"#   name: {name}\n"])
    lines.append("# ---\n")
    for cell in model["cells"]:
        if cell["cell_type"] == "markdown":
            marker = "# %% [markdown]"
        elif cell["cell_type"] == "raw":
            marker = "# %% [raw]"
        else:
            marker = "# %%"
        lines.append(f"{marker} {marker_json(cell)}\n")
        source = cell.get("source", "")
        if cell["cell_type"] == "markdown":
            if source == "":
                continue
            for raw in source.splitlines(keepends=True):
                lines.append("# " + raw)
            if not source.endswith("\n"):
                pass
        else:
            lines.append(source)
            if source and not source.endswith("\n"):
                lines.append("\n")
    return "".join(lines)


def notebook_json_text(model):
    return json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_model(path, model, fmt=None):
    fmt = fmt or format_of(path)
    if fmt == "ipynb":
        atomic_write_text(path, notebook_json_text(model))
    else:
        atomic_write_text(path, write_script_text(model))


def read_state(config):
    path = config["root"] / STATE_NAME
    if not path.exists():
        return {"pairs": {}}
    try:
        state = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed state file: {exc}") from exc
    if not isinstance(state, dict):
        return {"pairs": {}}
    pairs = state.get("pairs")
    if not isinstance(pairs, dict):
        state["pairs"] = {}
    return state


def state_path(config):
    return config["root"] / STATE_NAME


def update_state_entry(state, pair, ipynb_model, text_model):
    state.setdefault("pairs", {})[pair["key"]] = {
        "ipynb": pair["ipynb_rel"],
        "text": pair["text_rel"],
        "last_synced": {
            "ipynb_version": model_version(ipynb_model),
            "text_version": model_version(text_model),
            "ipynb_hash": stable_hash(ipynb_model),
            "text_hash": stable_hash(text_model),
        },
    }


def comparable_cell(cell, include_outputs=False):
    data = {
        "id": cell.get("id"),
        "cell_type": cell.get("cell_type"),
        "source": cell.get("source", ""),
        "tags": cell.get("metadata", {}).get("tags"),
        "name": cell.get("metadata", {}).get("name"),
    }
    if include_outputs and cell.get("cell_type") == "code":
        data["execution_count"] = cell.get("execution_count")
        data["outputs"] = cell.get("outputs", [])
    return data


def compare_models(a, b):
    differences = []
    if model_version(a) != model_version(b):
        differences.append("version")
    if a["metadata"]["minijupy"].get("formats") != b["metadata"]["minijupy"].get("formats"):
        differences.append("formats")
    if len(a["cells"]) != len(b["cells"]):
        differences.append("cell_count")
    for left, right in zip(a["cells"], b["cells"]):
        if left["cell_type"] != right["cell_type"]:
            differences.append("cell_type")
        if left.get("source", "") != right.get("source", ""):
            differences.append("source")
        if left.get("id") != right.get("id"):
            differences.append("id")
        if left.get("metadata", {}).get("tags") != right.get("metadata", {}).get("tags"):
            differences.append("tags")
        if left.get("metadata", {}).get("name") != right.get("metadata", {}).get("name"):
            differences.append("name")
    return sorted(set(differences))


def pair_object(pair, state, command, check_mode=False, explicit_source=None):
    exists = {"ipynb": pair["ipynb"].exists(), "text": pair["text"].exists()}
    if not exists["ipynb"] and not exists["text"]:
        raise MiniJupyError("both sides of pair are missing")
    errors = []
    ipynb_model = read_model(pair["ipynb"]) if exists["ipynb"] else None
    text_model = read_model(pair["text"]) if exists["text"] else None
    entry = state.get("pairs", {}).get(pair["key"], {})
    last = entry.get("last_synced", {}) if isinstance(entry, dict) else {}
    last_ipynb = last.get("ipynb_version")
    last_text = last.get("text_version")
    ipynb_version = model_version(ipynb_model) if ipynb_model else None
    text_version = model_version(text_model) if text_model else None
    conflict = False
    source = "none"
    if explicit_source:
        source = explicit_source
    elif not exists["ipynb"]:
        source = "text"
    elif not exists["text"]:
        source = "ipynb"
    elif last_ipynb is None or last_text is None:
        source = "none"
    else:
        ipynb_changed = ipynb_version > last_ipynb
        text_changed = text_version > last_text
        conflict = ipynb_changed and text_changed
        if conflict:
            source = "none"
        elif ipynb_changed:
            source = "ipynb"
        elif text_changed:
            source = "text"
    missing = []
    if not exists["ipynb"]:
        missing.append(pair["ipynb_rel"])
    if not exists["text"]:
        missing.append(pair["text_rel"])
    differences = []
    roundtrip_ok = True
    if missing:
        roundtrip_ok = False
    if ipynb_model and text_model:
        differences = compare_models(ipynb_model, text_model)
        roundtrip_ok = not differences
    if check_mode and last_ipynb is not None and ipynb_version is not None and last_ipynb > ipynb_version:
        differences.append("state")
        roundtrip_ok = False
    if check_mode and last_text is not None and text_version is not None and last_text > text_version:
        differences.append("state")
        roundtrip_ok = False
    planned = []
    if source == "ipynb":
        planned = [pair["text_rel"], STATE_NAME]
    elif source == "text":
        planned = [pair["ipynb_rel"], STATE_NAME]
    return {
        "ipynb": pair["ipynb_rel"],
        "text": pair["text_rel"],
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
        "differences": sorted(set(differences)),
        "errors": errors,
        "_models": {"ipynb": ipynb_model, "text": text_model},
    }


def public_pair_object(obj):
    copied = dict(obj)
    copied.pop("_models", None)
    return copied


def summary_for(pairs):
    return {
        "pairs": len(pairs),
        "conflicts": sum(1 for item in pairs if item["conflict"]),
        "missing": sum(1 for item in pairs if item["missing"]),
        "planned_writes": sum(len(item["planned_writes"]) for item in pairs),
        "errors": sum(1 for item in pairs if item["errors"]),
    }


def discover_pairs(config, state):
    root = config["root"]
    candidates = []
    if config["mapped"]:
        roots = [(root / config["notebook_dir"]), (root / config["script_dir"])]
    else:
        roots = [root]
    for base in roots:
        if not base.exists():
            continue
        for suffix in ("*.ipynb", "*.py"):
            candidates.extend(base.rglob(suffix))
    for entry in state.get("pairs", {}).values():
        if isinstance(entry, dict):
            ipynb = entry.get("ipynb")
            text = entry.get("text")
            if isinstance(ipynb, str):
                candidates.append(root / ipynb)
            if isinstance(text, str):
                candidates.append(root / text)
    pairs = {}
    for path in sorted(set(p.resolve() for p in candidates), key=lambda p: p.as_posix()):
        try:
            pair = counterpart_for(path, config)
        except MiniJupyError:
            raise
        existing = pairs.get(pair["key"])
        if existing and (existing["ipynb"] != pair["ipynb"] or existing["text"] != pair["text"]):
            raise MiniJupyError("duplicate paired paths")
        pairs[pair["key"]] = pair
    return [pairs[key] for key in sorted(pairs)]


def preserve_outputs(text_model, old_ipynb_model):
    new_model = copy.deepcopy(text_model)
    if old_ipynb_model is None:
        return new_model
    old_cells = old_ipynb_model["cells"]
    used = set()
    by_id = {}
    for index, cell in enumerate(old_cells):
        if cell["cell_type"] == "code":
            by_id[cell["id"]] = index
    for new_index, cell in enumerate(new_model["cells"]):
        if cell["cell_type"] != "code":
            continue
        match = None
        if cell["id"] in by_id and by_id[cell["id"]] not in used:
            match = by_id[cell["id"]]
        if match is None:
            wanted = hashlib.sha256(cell.get("source", "").encode("utf-8")).hexdigest()
            for old_index, old_cell in enumerate(old_cells):
                if old_index in used or old_cell["cell_type"] != cell["cell_type"]:
                    continue
                old_hash = hashlib.sha256(old_cell.get("source", "").encode("utf-8")).hexdigest()
                if old_hash == wanted:
                    match = old_index
                    break
        if match is None and new_index < len(old_cells):
            old_cell = old_cells[new_index]
            if new_index not in used and old_cell["cell_type"] == cell["cell_type"]:
                match = new_index
        if match is not None:
            used.add(match)
            old_cell = old_cells[match]
            cell["execution_count"] = old_cell.get("execution_count")
            cell["outputs"] = copy.deepcopy(old_cell.get("outputs", []))
        else:
            cell["execution_count"] = None
            cell["outputs"] = []
    return new_model


def command_inspect(args, config):
    path = Path(args.input)
    model = read_model(path)
    return {
        "ok": True,
        "command": "inspect",
        "path": rel_to(path if path.is_absolute() else (Path.cwd() / path), config["root"]),
        "format": format_of(path),
        "version": model_version(model),
        "notebook": model,
    }


def command_to_text(args, config):
    inp = Path(args.input)
    out = Path(args.output)
    if format_of(inp) != "ipynb" or out.suffix.lower() != ".py":
        raise MiniJupyError("unsupported command or option combination")
    model = read_model(inp)
    write_model(out, model, "text")
    return {"ok": True, "command": "to-text", "input": args.input, "output": args.output}


def command_to_ipynb(args, config):
    inp = Path(args.input)
    out = Path(args.output)
    if format_of(inp) != "text" or out.suffix.lower() != ".ipynb":
        raise MiniJupyError("unsupported command or option combination")
    model = read_model(inp)
    write_model(out, model, "ipynb")
    return {"ok": True, "command": "to-ipynb", "input": args.input, "output": args.output}


def command_pair(args, config):
    pair = counterpart_for(args.input, config)
    state = read_state(config)
    exists = {"ipynb": pair["ipynb"].exists(), "text": pair["text"].exists()}
    if not exists["ipynb"] and not exists["text"]:
        raise MiniJupyError("both sides of pair are missing")
    if exists["ipynb"]:
        ipynb_model = set_paired(read_model(pair["ipynb"]))
    else:
        text_model = set_paired(read_model(pair["text"]))
        ipynb_model = text_model
        write_model(pair["ipynb"], ipynb_model, "ipynb")
    if exists["text"]:
        text_model = set_paired(read_model(pair["text"]))
    else:
        text_model = copy.deepcopy(ipynb_model)
        write_model(pair["text"], text_model, "text")
    if exists["ipynb"]:
        write_model(pair["ipynb"], ipynb_model, "ipynb")
    if exists["text"]:
        write_model(pair["text"], text_model, "text")
    update_state_entry(state, pair, ipynb_model, text_model)
    atomic_write_json(state_path(config), state)
    obj = pair_object(pair, state, "pair")
    return {"ok": True, "command": "pair", "root": ".", "pairs": [public_pair_object(obj)], "summary": summary_for([obj])}


def status_or_check(args, config, check_mode=False):
    state = read_state(config)
    if args.all:
        if not args.config:
            raise MiniJupyError("--all requires --config")
        pair_paths = discover_pairs(config, state)
    elif args.input:
        pair_paths = [counterpart_for(args.input, config)]
    else:
        raise MiniJupyError("unsupported command or option combination")
    pairs = [pair_object(pair, state, args.command, check_mode=check_mode) for pair in pair_paths]
    public = [public_pair_object(pair) for pair in pairs]
    return {
        "ok": True,
        "command": "check" if check_mode else "status",
        "root": ".",
        "pairs": public,
        "summary": summary_for(public),
    }


def apply_sync_plan(pair, info, state):
    source = info["source"]
    if source == "none":
        return []
    ipynb_model = info["_models"]["ipynb"]
    text_model = info["_models"]["text"]
    writes = []
    if source == "ipynb":
        if ipynb_model is None:
            raise MiniJupyError("missing ipynb source")
        text_model = set_paired(copy.deepcopy(ipynb_model))
        ipynb_model = set_paired(ipynb_model)
        write_model(pair["text"], text_model, "text")
        if not pair["ipynb"].exists() or "formats" not in read_model(pair["ipynb"])["metadata"]["minijupy"]:
            write_model(pair["ipynb"], ipynb_model, "ipynb")
        writes.append(pair["text_rel"])
    elif source == "text":
        if text_model is None:
            raise MiniJupyError("missing text source")
        text_model = set_paired(text_model)
        ipynb_model = preserve_outputs(text_model, ipynb_model)
        ipynb_model = set_paired(ipynb_model)
        write_model(pair["ipynb"], ipynb_model, "ipynb")
        writes.append(pair["ipynb_rel"])
    update_state_entry(state, pair, ipynb_model, text_model)
    writes.append(STATE_NAME)
    return writes


def command_sync(args, config):
    state = read_state(config)
    if args.all:
        if not args.config:
            raise MiniJupyError("--all requires --config")
        pair_paths = discover_pairs(config, state)
    elif args.input:
        pair_paths = [counterpart_for(args.input, config)]
    else:
        raise MiniJupyError("unsupported command or option combination")
    explicit = args.source
    infos = []
    for pair in pair_paths:
        info = pair_object(pair, state, "sync", explicit_source=explicit)
        if info["conflict"] and explicit is None:
            raise MiniJupyError("conflict without explicit source")
        if not explicit and info["source"] == "none":
            entry = state.get("pairs", {}).get(pair["key"])
            if entry is None and info["exists"]["ipynb"] and info["exists"]["text"]:
                raise MiniJupyError("unpaired files require pair or explicit source")
        if explicit == "ipynb" and not info["exists"]["ipynb"]:
            raise MiniJupyError("missing ipynb source")
        if explicit == "text" and not info["exists"]["text"]:
            raise MiniJupyError("missing text source")
        infos.append((pair, info))
    public_pairs = []
    any_state = False
    for pair, info in infos:
        writes = apply_sync_plan(pair, info, state)
        any_state = any_state or STATE_NAME in writes
        refreshed = pair_object(pair, state, "sync")
        refreshed["planned_writes"] = writes
        public_pairs.append(public_pair_object(refreshed))
    if any_state:
        atomic_write_json(state_path(config), state)
    return {"ok": True, "command": "sync", "root": ".", "pairs": public_pairs, "summary": summary_for(public_pairs)}


def build_parser():
    parser = argparse.ArgumentParser(prog="minijupy.py")
    parser.add_argument("command")
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--config")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--source", choices=["ipynb", "text"])
    return parser


def run(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    config = parse_config(args.config)
    command = args.command
    if command == "inspect":
        if not args.input or args.output or args.all or args.source:
            raise MiniJupyError("unsupported command or option combination")
        return command_inspect(args, config)
    if command == "to-text":
        if not args.input or not args.output or args.all or args.source:
            raise MiniJupyError("unsupported command or option combination")
        return command_to_text(args, config)
    if command == "to-ipynb":
        if not args.input or not args.output or args.all or args.source:
            raise MiniJupyError("unsupported command or option combination")
        return command_to_ipynb(args, config)
    if command == "pair":
        if not args.input or args.output or args.all or args.source:
            raise MiniJupyError("unsupported command or option combination")
        return command_pair(args, config)
    if command == "status":
        if args.output or args.source or bool(args.input) == bool(args.all):
            raise MiniJupyError("unsupported command or option combination")
        return status_or_check(args, config, check_mode=False)
    if command == "check":
        if args.output or args.source or bool(args.input) == bool(args.all):
            raise MiniJupyError("unsupported command or option combination")
        return status_or_check(args, config, check_mode=True)
    if command == "sync":
        if args.output or bool(args.input) == bool(args.all):
            raise MiniJupyError("unsupported command or option combination")
        return command_sync(args, config)
    raise MiniJupyError("unsupported command")


def main(argv=None):
    try:
        result = run(sys.argv[1:] if argv is None else argv)
    except MiniJupyError as exc:
        return fail(str(exc))
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

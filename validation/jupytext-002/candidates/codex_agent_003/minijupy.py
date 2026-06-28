#!/usr/bin/env python3
import argparse
import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path


FORMATS = "ipynb,py:percent"
STATE_NAME = ".minijupy-state.json"


class MiniError(Exception):
    pass


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def relpath(path, root):
    return Path(os.path.relpath(Path(path).resolve(strict=False), Path(root).resolve(strict=False))).as_posix()


def clean_rel(path):
    return Path(path).as_posix()


def parse_version(value, where):
    if value is None:
        return 1
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MiniError(f"invalid version in {where}")
    return value


def parse_config(config_path):
    if not config_path:
        return {
            "root": Path.cwd().resolve(),
            "formats": FORMATS,
            "notebook_dir": None,
            "script_dir": None,
        }

    path = Path(config_path).resolve(strict=False)
    if not path.exists():
        raise MiniError(f"config not found: {config_path}")
    values = {}
    allowed = {"formats", "notebook_dir", "script_dir"}
    for lineno, raw in enumerate(read_text(path).splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', line)
        if not match:
            raise MiniError(f"invalid config line {lineno}")
        key, value = match.groups()
        if key not in allowed:
            raise MiniError(f"invalid config key: {key}")
        values[key] = value
    formats = values.get("formats", FORMATS)
    if formats not in (FORMATS, "py:percent,ipynb"):
        raise MiniError("invalid config formats")
    has_nb = "notebook_dir" in values
    has_py = "script_dir" in values
    if has_nb != has_py:
        raise MiniError("invalid config: notebook_dir and script_dir must be supplied together")
    return {
        "root": path.parent.resolve(),
        "formats": formats,
        "notebook_dir": values.get("notebook_dir"),
        "script_dir": values.get("script_dir"),
    }


def state_path(cfg):
    return cfg["root"] / STATE_NAME


def load_state(cfg):
    path = state_path(cfg)
    if not path.exists():
        return {"pairs": {}}
    try:
        data = json.loads(read_text(path))
    except Exception as exc:
        raise MiniError(f"malformed state file: {exc}")
    if not isinstance(data, dict):
        raise MiniError("malformed state file")
    pairs = data.get("pairs", {})
    if not isinstance(pairs, dict):
        raise MiniError("malformed state file")
    return {"pairs": pairs}


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        finally:
            raise


def atomic_write_json(path, data):
    atomic_write(path, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def normalize_source(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(part, str) for part in value):
        return "".join(value)
    raise MiniError("invalid cell source")


def normalize_cell_metadata(value):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise MiniError("invalid cell metadata")
    out = {}
    if "tags" in value:
        tags = value["tags"]
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise MiniError("invalid cell tags")
        out["tags"] = list(tags)
    if "name" in value:
        if not isinstance(value["name"], str):
            raise MiniError("invalid cell name")
        out["name"] = value["name"]
    return out


def normalize_minijupy_metadata(metadata, where):
    mj = metadata.get("minijupy", {}) if isinstance(metadata, dict) else {}
    if mj is None:
        mj = {}
    if not isinstance(mj, dict):
        raise MiniError(f"invalid minijupy metadata in {where}")
    version = parse_version(mj.get("version"), where)
    out = {"version": version}
    formats = mj.get("formats")
    if formats is not None:
        if formats not in (FORMATS, "py:percent,ipynb"):
            raise MiniError(f"invalid formats in {where}")
        out["formats"] = formats
    return out


def normalize_notebook(raw, where="notebook"):
    if not isinstance(raw, dict):
        raise MiniError("malformed notebook")
    if raw.get("nbformat") != 4:
        raise MiniError("unsupported notebook nbformat")
    metadata = raw.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise MiniError("invalid notebook metadata")
    cells = raw.get("cells", [])
    if not isinstance(cells, list):
        raise MiniError("invalid notebook cells")
    seen = set()
    out_cells = []
    for index, cell in enumerate(cells, 1):
        if not isinstance(cell, dict):
            raise MiniError("invalid cell")
        ctype = cell.get("cell_type")
        if ctype not in ("code", "markdown", "raw"):
            raise MiniError("unsupported cell type")
        cid = cell.get("id") or f"c{index}"
        if not isinstance(cid, str):
            raise MiniError("invalid cell id")
        if cid in seen:
            raise MiniError("duplicate cell id")
        seen.add(cid)
        normalized = {
            "id": cid,
            "cell_type": ctype,
            "source": normalize_source(cell.get("source", "")),
            "metadata": normalize_cell_metadata(cell.get("metadata", {})),
        }
        if ctype == "code":
            normalized["execution_count"] = cell.get("execution_count")
            outputs = cell.get("outputs", [])
            normalized["outputs"] = copy.deepcopy(outputs if isinstance(outputs, list) else [])
        out_cells.append(normalized)
    out_meta = {
        "kernelspec": copy.deepcopy(metadata.get("kernelspec") if isinstance(metadata.get("kernelspec"), dict) else {}),
        "language_info": copy.deepcopy(metadata.get("language_info") if isinstance(metadata.get("language_info"), dict) else {}),
        "minijupy": normalize_minijupy_metadata(metadata, where),
    }
    return {
        "nbformat": 4,
        "nbformat_minor": raw.get("nbformat_minor", 5),
        "metadata": out_meta,
        "cells": out_cells,
    }


def read_ipynb(path):
    try:
        raw = json.loads(read_text(path))
    except Exception as exc:
        raise MiniError(f"malformed JSON notebook: {exc}")
    return normalize_notebook(raw, str(path))


def parse_scalar(value):
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_percent_header(lines):
    meta = {}
    start = 0
    if not lines or lines[0].strip() != "# ---":
        return meta, 0
    current = None
    end = None
    for index in range(1, len(lines)):
        stripped = lines[index].rstrip("\n")
        if stripped.strip() == "# ---":
            end = index + 1
            break
        if stripped.startswith("#"):
            body = stripped[1:]
            if body.startswith(" "):
                body = body[1:]
        else:
            body = stripped
        if not body.strip():
            continue
        section = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):", body.strip())
        if section:
            current = section.group(1)
            continue
        item = re.fullmatch(r"\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)", body)
        if item and current:
            meta.setdefault(current, {})[item.group(1)] = parse_scalar(item.group(2))
    if end is None:
        return {}, 0
    return meta, end


MARKER_RE = re.compile(r"^# %%(?:\s+\[([A-Za-z]+)\])?(?:\s+(\{.*\}))?\s*$")


def marker_from_line(line):
    match = MARKER_RE.match(line.rstrip("\n"))
    if not match:
        if line.startswith("# %%"):
            raise MiniError("malformed percent marker")
        return None
    bracket, raw_json = match.groups()
    if bracket is None:
        ctype = "code"
    elif bracket in ("markdown", "md"):
        ctype = "markdown"
    elif bracket == "raw":
        ctype = "raw"
    else:
        raise MiniError("unsupported percent cell type")
    meta = {}
    if raw_json:
        try:
            meta = json.loads(raw_json)
        except Exception as exc:
            raise MiniError(f"malformed percent marker JSON: {exc}")
        if not isinstance(meta, dict):
            raise MiniError("malformed percent marker JSON")
        for key in meta:
            if key not in ("id", "tags", "name"):
                raise MiniError(f"unsupported marker key: {key}")
    return ctype, meta


def finalize_percent_cell(cells, ctype, marker_meta, body_lines):
    source = "".join(body_lines)
    if ctype == "markdown":
        converted = []
        for line in body_lines:
            converted.append(line[2:] if line.startswith("# ") else line)
        source = "".join(converted)
    cell = {
        "cell_type": ctype,
        "source": source,
        "metadata": {},
    }
    if "id" in marker_meta:
        cell["id"] = marker_meta["id"]
    meta = {}
    if "tags" in marker_meta:
        meta["tags"] = marker_meta["tags"]
    if "name" in marker_meta:
        meta["name"] = marker_meta["name"]
    if meta:
        cell["metadata"] = meta
    if ctype == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
    cells.append(cell)


def read_percent(path):
    lines = read_text(path).splitlines(True)
    header, start = parse_percent_header(lines)
    nb_meta = {
        "kernelspec": {},
        "language_info": {},
        "minijupy": {},
    }
    if isinstance(header.get("minijupy"), dict):
        if "formats" in header["minijupy"]:
            nb_meta["minijupy"]["formats"] = header["minijupy"]["formats"]
        if "version" in header["minijupy"]:
            nb_meta["minijupy"]["version"] = header["minijupy"]["version"]
    if isinstance(header.get("kernelspec"), dict) and "name" in header["kernelspec"]:
        nb_meta["kernelspec"]["name"] = header["kernelspec"]["name"]

    cells = []
    current_type = None
    current_meta = {}
    body = []
    pre = []
    for line in lines[start:]:
        marker = marker_from_line(line)
        if marker is not None:
            if current_type is None:
                if pre and any(part.strip() for part in pre):
                    finalize_percent_cell(cells, "code", {}, pre)
                pre = []
            else:
                finalize_percent_cell(cells, current_type, current_meta, body)
            current_type, current_meta = marker
            body = []
            continue
        if current_type is None:
            pre.append(line)
        else:
            body.append(line)
    if current_type is None:
        if pre and any(part.strip() for part in pre):
            finalize_percent_cell(cells, "code", {}, pre)
    else:
        finalize_percent_cell(cells, current_type, current_meta, body)
    raw = {"nbformat": 4, "metadata": nb_meta, "cells": cells}
    return normalize_notebook(raw, str(path))


def read_model(path):
    path = Path(path)
    if path.suffix == ".ipynb":
        return read_ipynb(path), "ipynb"
    if path.suffix == ".py":
        return read_percent(path), "text"
    raise MiniError(f"unsupported file type: {path}")


def set_formats(model):
    updated = copy.deepcopy(model)
    updated.setdefault("metadata", {}).setdefault("minijupy", {})["formats"] = FORMATS
    return updated


def model_version(model):
    return parse_version(model["metadata"].get("minijupy", {}).get("version"), "model")


def model_formats(model):
    return model["metadata"].get("minijupy", {}).get("formats")


def notebook_json(model):
    return json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def marker_json(cell):
    meta = {"id": cell["id"]}
    if cell.get("metadata", {}).get("tags") is not None:
        meta["tags"] = cell["metadata"]["tags"]
    if cell.get("metadata", {}).get("name") is not None:
        meta["name"] = cell["metadata"]["name"]
    return json.dumps(meta, sort_keys=True, ensure_ascii=False)


def write_markdown_source(source):
    if not source:
        return ""
    parts = []
    for line in source.splitlines(True):
        parts.append("# " + line)
    if not source.endswith("\n"):
        # splitlines(True) keeps the final partial line; the prefix above is enough.
        pass
    return "".join(parts)


def percent_text(model):
    mj = model["metadata"].get("minijupy", {})
    version = parse_version(mj.get("version"), "percent writer")
    formats = mj.get("formats", FORMATS)
    lines = [
        "# ---\n",
        "# minijupy:\n",
        f"#   formats: {formats}\n",
        f"#   version: {version}\n",
    ]
    name = model["metadata"].get("kernelspec", {}).get("name")
    if isinstance(name, str):
        lines.extend(["# kernelspec:\n", f"#   name: {name}\n"])
    lines.append("# ---\n")
    for index, cell in enumerate(model["cells"]):
        if index > 0 and lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        ctype = cell["cell_type"]
        if ctype == "code":
            marker = "# %%"
        elif ctype == "markdown":
            marker = "# %% [markdown]"
        else:
            marker = "# %% [raw]"
        marker += " " + marker_json(cell)
        lines.append(marker + "\n")
        if ctype == "markdown":
            lines.append(write_markdown_source(cell["source"]))
        else:
            lines.append(cell["source"])
        if index < len(model["cells"]) - 1 and lines and lines[-1] and not lines[-1].endswith("\n"):
            lines.append("\n")
    return "".join(lines)


def hash_model(model):
    payload = json.dumps(model, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_for_compare(model, include_outputs=False):
    data = {
        "version": model_version(model),
        "formats": model_formats(model),
        "cells": [],
    }
    for cell in model["cells"]:
        item = {
            "id": cell["id"],
            "cell_type": cell["cell_type"],
            "source": cell["source"],
            "tags": cell.get("metadata", {}).get("tags"),
            "name": cell.get("metadata", {}).get("name"),
        }
        if include_outputs and cell["cell_type"] == "code":
            item["execution_count"] = cell.get("execution_count")
            item["outputs"] = cell.get("outputs", [])
        data["cells"].append(item)
    return data


def compare_models(ipynb_model, text_model):
    diffs = []
    left = canonical_for_compare(ipynb_model)
    right = canonical_for_compare(text_model)
    if left["version"] != right["version"]:
        diffs.append("version")
    if left["formats"] != right["formats"]:
        diffs.append("formats")
    if len(left["cells"]) != len(right["cells"]):
        diffs.append("cell_count")
    for a, b in zip(left["cells"], right["cells"]):
        for key in ("cell_type", "source", "id", "tags", "name"):
            if a.get(key) != b.get(key) and key not in diffs:
                diffs.append(key)
    return diffs


def path_pair(input_path, cfg):
    root = cfg["root"]
    path = Path(input_path).resolve(strict=False)
    suffix = path.suffix
    if suffix not in (".ipynb", ".py"):
        raise MiniError("unsupported file type")

    nb_dir = cfg.get("notebook_dir")
    py_dir = cfg.get("script_dir")
    if nb_dir is not None:
        nb_root = (root / nb_dir).resolve(strict=False)
        py_root = (root / py_dir).resolve(strict=False)
        try:
            if suffix == ".ipynb":
                sub = path.relative_to(nb_root)
                ipynb = path
                text = py_root / sub.with_suffix(".py")
            else:
                sub = path.relative_to(py_root)
                text = path
                ipynb = nb_root / sub.with_suffix(".ipynb")
        except ValueError:
            raise MiniError("path mismatch")
    else:
        if suffix == ".ipynb":
            ipynb = path
            text = path.with_suffix(".py")
        else:
            text = path
            ipynb = path.with_suffix(".ipynb")
    return {
        "ipynb_abs": ipynb,
        "text_abs": text,
        "ipynb": relpath(ipynb, root),
        "text": relpath(text, root),
        "key": relpath(ipynb, root),
    }


def discover_pairs(cfg):
    if cfg.get("notebook_dir") is not None:
        roots = [cfg["root"] / cfg["notebook_dir"], cfg["root"] / cfg["script_dir"]]
    else:
        roots = [cfg["root"]]
    by_key = {}
    seen_files = set()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in (".ipynb", ".py"):
                continue
            resolved = path.resolve(strict=False)
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            pair = path_pair(resolved, cfg)
            existing = by_key.get(pair["key"])
            if existing and (existing["ipynb"] != pair["ipynb"] or existing["text"] != pair["text"]):
                raise MiniError("duplicate mapping")
            by_key[pair["key"]] = pair
    return [by_key[key] for key in sorted(by_key)]


def state_entry_for(pair, state):
    entry = state.get("pairs", {}).get(pair["key"])
    return entry if isinstance(entry, dict) else None


def versions_for(pair):
    versions = {"ipynb": None, "text": None}
    models = {"ipynb": None, "text": None}
    if pair["ipynb_abs"].exists():
        models["ipynb"] = read_ipynb(pair["ipynb_abs"])
        versions["ipynb"] = model_version(models["ipynb"])
    if pair["text_abs"].exists():
        models["text"] = read_percent(pair["text_abs"])
        versions["text"] = model_version(models["text"])
    return models, versions


def choose_source(pair, state, models, versions, explicit=None):
    exists = {"ipynb": models["ipynb"] is not None, "text": models["text"] is not None}
    if explicit:
        if not exists[explicit]:
            raise MiniError(f"selected source is missing: {explicit}")
        return explicit, False, []
    if not exists["ipynb"] and not exists["text"]:
        raise MiniError("both sides are missing")
    if exists["ipynb"] and not exists["text"]:
        return "ipynb", False, [pair["text"]]
    if exists["text"] and not exists["ipynb"]:
        return "text", False, [pair["ipynb"]]

    entry = state_entry_for(pair, state)
    if not entry:
        return "none", False, []
    last = entry.get("last_synced", {}) if isinstance(entry.get("last_synced", {}), dict) else {}
    last_ipynb = last.get("ipynb_version")
    last_text = last.get("text_version")
    ip_changed = isinstance(last_ipynb, int) and versions["ipynb"] > last_ipynb
    text_changed = isinstance(last_text, int) and versions["text"] > last_text
    if ip_changed and text_changed:
        return "none", True, []
    if ip_changed:
        return "ipynb", False, []
    if text_changed:
        return "text", False, []
    return "none", False, []


def planned_writes(pair, source, conflict, command_is_sync=False):
    if conflict or source == "none":
        return []
    writes = []
    if source == "ipynb":
        writes.append(pair["text"])
    elif source == "text":
        writes.append(pair["ipynb"])
    writes.append(STATE_NAME)
    return writes


def pair_status(pair, cfg, state, command="status", explicit_source=None, for_sync=False):
    errors = []
    differences = []
    try:
        models, versions = versions_for(pair)
        source, conflict, missing_from_source = choose_source(pair, state, models, versions, explicit_source)
    except MiniError as exc:
        models = {"ipynb": None, "text": None}
        versions = {"ipynb": None, "text": None}
        source = "none"
        conflict = False
        missing_from_source = []
        errors.append(str(exc))

    exists = {"ipynb": models["ipynb"] is not None, "text": models["text"] is not None}
    missing = []
    if not exists["ipynb"]:
        missing.append(pair["ipynb"])
    if not exists["text"]:
        missing.append(pair["text"])

    entry = state_entry_for(pair, state)
    last = entry.get("last_synced", {}) if entry and isinstance(entry.get("last_synced", {}), dict) else {}
    if command == "check":
        if not errors:
            if not exists["ipynb"] or not exists["text"]:
                differences.append("missing")
            else:
                differences.extend(compare_models(models["ipynb"], models["text"]))
            if entry:
                if isinstance(last.get("ipynb_version"), int) and versions["ipynb"] is not None and last["ipynb_version"] > versions["ipynb"]:
                    differences.append("state")
                if isinstance(last.get("text_version"), int) and versions["text"] is not None and last["text_version"] > versions["text"]:
                    differences.append("state")
    roundtrip_ok = not errors and not differences and not conflict and not missing
    if command == "status":
        roundtrip_ok = not errors and not conflict
    planned = planned_writes(pair, source, conflict)
    if source != "none" and missing_from_source:
        planned = planned_writes(pair, source, conflict)
    return {
        "ipynb": pair["ipynb"],
        "text": pair["text"],
        "exists": exists,
        "versions": {
            "ipynb": versions["ipynb"],
            "text": versions["text"],
            "last_ipynb": last.get("ipynb_version"),
            "last_text": last.get("text_version"),
        },
        "source": source if not conflict else "none",
        "conflict": conflict,
        "missing": missing,
        "planned_writes": planned,
        "roundtrip_ok": roundtrip_ok,
        "differences": sorted(set(differences), key=differences.index),
        "errors": errors,
    }


def summary_for(pairs):
    return {
        "pairs": len(pairs),
        "conflicts": sum(1 for item in pairs if item["conflict"]),
        "missing": sum(len(item["missing"]) for item in pairs),
        "planned_writes": sum(len(item["planned_writes"]) for item in pairs),
        "errors": sum(len(item["errors"]) for item in pairs),
    }


def output(obj):
    print(json.dumps(obj, sort_keys=True, ensure_ascii=False))


def command_inspect(args):
    cfg = parse_config(args.config)
    model, fmt = read_model(args.input)
    output({
        "ok": True,
        "command": "inspect",
        "path": relpath(args.input, cfg["root"]),
        "format": fmt,
        "version": model_version(model),
        "notebook": model,
    })


def command_to_text(args):
    parse_config(args.config)
    if Path(args.input).suffix != ".ipynb" or Path(args.output).suffix != ".py":
        raise MiniError("invalid to-text input or output")
    model = read_ipynb(args.input)
    atomic_write(args.output, percent_text(model))
    output({"ok": True, "command": "to-text", "input": args.input, "output": args.output})


def command_to_ipynb(args):
    parse_config(args.config)
    if Path(args.input).suffix != ".py" or Path(args.output).suffix != ".ipynb":
        raise MiniError("invalid to-ipynb input or output")
    model = read_percent(args.input)
    atomic_write(args.output, notebook_json(model))
    output({"ok": True, "command": "to-ipynb", "input": args.input, "output": args.output})


def update_state_entry(state, pair, ipynb_model, text_model):
    state.setdefault("pairs", {})[pair["key"]] = {
        "ipynb": pair["ipynb"],
        "text": pair["text"],
        "last_synced": {
            "ipynb_version": model_version(ipynb_model),
            "text_version": model_version(text_model),
            "ipynb_hash": hash_model(ipynb_model),
            "text_hash": hash_model(text_model),
        },
    }


def command_pair(args):
    cfg = parse_config(args.config)
    state = load_state(cfg)
    pair = path_pair(args.input, cfg)
    ip_exists = pair["ipynb_abs"].exists()
    text_exists = pair["text_abs"].exists()
    if not ip_exists and not text_exists:
        raise MiniError("both sides are missing")
    writes = []
    if ip_exists:
        ip_model = set_formats(read_ipynb(pair["ipynb_abs"]))
    else:
        ip_model = None
    if text_exists:
        text_model = set_formats(read_percent(pair["text_abs"]))
    else:
        text_model = None
    if ip_model is None:
        ip_model = set_formats(text_model)
        writes.append((pair["ipynb_abs"], notebook_json(ip_model)))
    elif not ip_exists or model_formats(read_ipynb(pair["ipynb_abs"])) != FORMATS:
        writes.append((pair["ipynb_abs"], notebook_json(ip_model)))
    if text_model is None:
        text_model = set_formats(ip_model)
        writes.append((pair["text_abs"], percent_text(text_model)))
    elif model_formats(read_percent(pair["text_abs"])) != FORMATS:
        writes.append((pair["text_abs"], percent_text(text_model)))
    update_state_entry(state, pair, ip_model, text_model)
    writes.append((state_path(cfg), json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"))
    for path, content in writes:
        atomic_write(path, content)
    item = pair_status(pair, cfg, load_state(cfg), "status")
    item["planned_writes"] = [clean_rel(relpath(path, cfg["root"])) if Path(path).is_absolute() else clean_rel(path) for path, _ in writes]
    output({"ok": True, "command": "pair", "root": ".", "pairs": [item], "summary": summary_for([item])})


def command_status_or_check(args, command):
    cfg = parse_config(args.config)
    if args.all and not args.config:
        raise MiniError("--all requires --config")
    state = load_state(cfg)
    pairs = discover_pairs(cfg) if args.all else [path_pair(args.input, cfg)]
    items = [pair_status(pair, cfg, state, command) for pair in pairs]
    if any(item["errors"] for item in items):
        raise MiniError("; ".join(err for item in items for err in item["errors"]))
    output({"ok": True, "command": command, "root": ".", "pairs": items, "summary": summary_for(items)})


def source_hash(cell):
    return hashlib.sha256((cell["cell_type"] + "\0" + cell["source"]).encode("utf-8")).hexdigest()


def preserve_outputs(new_model, old_model):
    result = copy.deepcopy(new_model)
    if old_model is None:
        return result
    old_cells = old_model["cells"]
    used = set()
    by_id = {cell["id"]: i for i, cell in enumerate(old_cells) if cell["cell_type"] == "code"}
    for pos, cell in enumerate(result["cells"]):
        if cell["cell_type"] != "code":
            continue
        match = None
        cid = cell.get("id")
        if cid in by_id and by_id[cid] not in used:
            match = by_id[cid]
        if match is None:
            h = source_hash(cell)
            for i, old in enumerate(old_cells):
                if i in used or old["cell_type"] != "code":
                    continue
                if source_hash(old) == h:
                    match = i
                    break
        if match is None and pos < len(old_cells):
            old = old_cells[pos]
            if pos not in used and old["cell_type"] == "code" and old["cell_type"] == cell["cell_type"]:
                match = pos
        if match is not None:
            used.add(match)
            old = old_cells[match]
            cell["execution_count"] = old.get("execution_count")
            cell["outputs"] = copy.deepcopy(old.get("outputs", []))
        else:
            cell["execution_count"] = None
            cell["outputs"] = []
    return result


def build_sync_writes(pair, cfg, state, explicit_source=None):
    models, versions = versions_for(pair)
    source, conflict, _missing = choose_source(pair, state, models, versions, explicit_source)
    if conflict:
        raise MiniError(f"conflict without explicit source: {pair['key']}")
    if source == "none":
        return [], source
    writes = []
    if source == "ipynb":
        ip_model = models["ipynb"]
        text_model = set_formats(ip_model)
        writes.append((pair["text_abs"], percent_text(text_model)))
        update_state_entry(state, pair, ip_model, read_percent_from_content(percent_text(text_model), str(pair["text_abs"])))
    elif source == "text":
        text_model = models["text"]
        ip_model = preserve_outputs(set_formats(text_model), models["ipynb"])
        writes.append((pair["ipynb_abs"], notebook_json(ip_model)))
        update_state_entry(state, pair, ip_model, text_model)
    return writes, source


def read_percent_from_content(content, where):
    tmp_lines = content.splitlines(True)
    header, start = parse_percent_header(tmp_lines)
    nb_meta = {"kernelspec": {}, "language_info": {}, "minijupy": {}}
    if isinstance(header.get("minijupy"), dict):
        nb_meta["minijupy"].update(header["minijupy"])
    if isinstance(header.get("kernelspec"), dict) and "name" in header["kernelspec"]:
        nb_meta["kernelspec"]["name"] = header["kernelspec"]["name"]
    cells = []
    current_type = None
    current_meta = {}
    body = []
    pre = []
    for line in tmp_lines[start:]:
        marker = marker_from_line(line)
        if marker is not None:
            if current_type is None:
                if pre and any(part.strip() for part in pre):
                    finalize_percent_cell(cells, "code", {}, pre)
            else:
                finalize_percent_cell(cells, current_type, current_meta, body)
            current_type, current_meta = marker
            body = []
            pre = []
        elif current_type is None:
            pre.append(line)
        else:
            body.append(line)
    if current_type is None:
        if pre and any(part.strip() for part in pre):
            finalize_percent_cell(cells, "code", {}, pre)
    else:
        finalize_percent_cell(cells, current_type, current_meta, body)
    return normalize_notebook({"nbformat": 4, "metadata": nb_meta, "cells": cells}, where)


def command_sync(args):
    cfg = parse_config(args.config)
    if args.all and not args.config:
        raise MiniError("--all requires --config")
    state = load_state(cfg)
    pairs = discover_pairs(cfg) if args.all else [path_pair(args.input, cfg)]
    writes = []
    sources = {}
    writes_by_pair = {}
    for pair in pairs:
        pair_writes, source = build_sync_writes(pair, cfg, state, args.source)
        sources[pair["key"]] = source
        writes_by_pair[pair["key"]] = [relpath(path, cfg["root"]) for path, _ in pair_writes]
        writes.extend(pair_writes)
    if writes:
        writes.append((state_path(cfg), json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"))
        for key, value in writes_by_pair.items():
            if value:
                value.append(STATE_NAME)
    for path, content in writes:
        atomic_write(path, content)
    new_state = load_state(cfg)
    items = []
    for pair in pairs:
        item = pair_status(pair, cfg, new_state, "status")
        item["planned_writes"] = writes_by_pair.get(pair["key"], [])
        item["source"] = sources.get(pair["key"], item["source"])
        items.append(item)
    output({"ok": True, "command": "sync", "root": ".", "pairs": items, "summary": summary_for(items)})


def build_parser():
    parser = argparse.ArgumentParser(prog="minijupy.py")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inspect")
    p.add_argument("--input", required=True)
    p.add_argument("--config")
    p = sub.add_parser("to-text")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--config")
    p = sub.add_parser("to-ipynb")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--config")
    p = sub.add_parser("pair")
    p.add_argument("--input", required=True)
    p.add_argument("--config")
    for name in ("status", "check"):
        p = sub.add_parser(name)
        group = p.add_mutually_exclusive_group(required=True)
        group.add_argument("--input")
        group.add_argument("--all", action="store_true")
        p.add_argument("--config")
    p = sub.add_parser("sync")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--input")
    group.add_argument("--all", action="store_true")
    p.add_argument("--config")
    p.add_argument("--source", choices=("ipynb", "text"))
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            command_inspect(args)
        elif args.command == "to-text":
            command_to_text(args)
        elif args.command == "to-ipynb":
            command_to_ipynb(args)
        elif args.command == "pair":
            command_pair(args)
        elif args.command == "status":
            command_status_or_check(args, "status")
        elif args.command == "check":
            command_status_or_check(args, "check")
        elif args.command == "sync":
            command_sync(args)
        else:
            raise MiniError("unsupported command")
    except MiniError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

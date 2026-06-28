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


class MiniJupyError(Exception):
    pass


def fail(message):
    print(message, file=sys.stderr)
    return 1


def stable_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_model(model):
    return hashlib.sha256(stable_json(model).encode("utf-8")).hexdigest()


def is_int_version(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def ensure_parent(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def atomic_write(path, data):
    path = Path(path)
    ensure_parent(path)
    tmp = path.with_name(path.name + ".tmp-minijupy")
    try:
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def atomic_write_many(writes):
    for path, data in writes.items():
        atomic_write(path, data)


def relpath(path, root):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        raise MiniJupyError(f"path mismatch: {path} is outside project root")


def load_config(config_path):
    if not config_path:
        root = Path.cwd().resolve()
        return {"root": root, "formats": FORMATS, "notebook_dir": None, "script_dir": None}

    config = Path(config_path).resolve()
    if not config.exists():
        raise MiniJupyError(f"config not found: {config_path}")
    values = {}
    for lineno, line in enumerate(config.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', stripped)
        if not m:
            raise MiniJupyError(f"invalid config line {lineno}")
        key, value = m.group(1), m.group(2)
        if key not in {"formats", "notebook_dir", "script_dir"}:
            raise MiniJupyError(f"invalid config key: {key}")
        if key in values:
            raise MiniJupyError(f"duplicate config key: {key}")
        values[key] = value

    formats = values.get("formats", FORMATS)
    if formats not in {FORMATS, "py:percent,ipynb"}:
        raise MiniJupyError("invalid config formats")
    has_nb = "notebook_dir" in values
    has_py = "script_dir" in values
    if has_nb != has_py:
        raise MiniJupyError("invalid config: notebook_dir and script_dir must be supplied together")
    if has_nb and values["notebook_dir"].strip("/") == values["script_dir"].strip("/"):
        raise MiniJupyError("invalid config: notebook_dir and script_dir must differ")
    return {
        "root": config.parent,
        "formats": formats,
        "notebook_dir": values.get("notebook_dir"),
        "script_dir": values.get("script_dir"),
    }


def state_path(cfg):
    return Path(cfg["root"]) / STATE_NAME


def load_state(cfg):
    path = state_path(cfg)
    if not path.exists():
        return {"pairs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed state file: {exc}")
    if not isinstance(data, dict):
        return {"pairs": {}}
    pairs = data.get("pairs")
    if not isinstance(pairs, dict):
        pairs = {}
    return {"pairs": pairs}


def dump_state(state):
    return json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def pair_for_path(path, cfg):
    p = Path(path).resolve()
    root = Path(cfg["root"]).resolve()
    suffix = p.suffix
    if suffix not in {".ipynb", ".py"}:
        raise MiniJupyError("unsupported file extension")

    if cfg["notebook_dir"] is None:
        rel = relpath(p, root)
        base = rel[:-len(suffix)]
        return {
            "ipynb": base + ".ipynb",
            "text": base + ".py",
            "key": base + ".ipynb",
        }

    nb_root = (root / cfg["notebook_dir"]).resolve()
    py_root = (root / cfg["script_dir"]).resolve()
    if suffix == ".ipynb":
        try:
            inner = p.relative_to(nb_root)
        except ValueError:
            raise MiniJupyError("path mismatch: notebook is outside notebook_dir")
        if inner.suffix != ".ipynb":
            raise MiniJupyError("unsupported notebook path")
        stem = inner.as_posix()[:-6]
    else:
        try:
            inner = p.relative_to(py_root)
        except ValueError:
            raise MiniJupyError("path mismatch: script is outside script_dir")
        if inner.suffix != ".py":
            raise MiniJupyError("unsupported script path")
        stem = inner.as_posix()[:-3]
    return {
        "ipynb": (Path(cfg["notebook_dir"]) / (stem + ".ipynb")).as_posix(),
        "text": (Path(cfg["script_dir"]) / (stem + ".py")).as_posix(),
        "key": (Path(cfg["notebook_dir"]) / (stem + ".ipynb")).as_posix(),
    }


def abs_pair(pair, cfg):
    root = Path(cfg["root"])
    return root / pair["ipynb"], root / pair["text"]


def normalize_source(source):
    if source is None:
        return ""
    if isinstance(source, str):
        return source
    if isinstance(source, list) and all(isinstance(x, str) for x in source):
        return "".join(source)
    raise MiniJupyError("invalid cell source")


def normalize_metadata(meta):
    out = {}
    if isinstance(meta, dict):
        tags = meta.get("tags")
        name = meta.get("name")
        if isinstance(tags, list) and all(isinstance(x, str) for x in tags):
            out["tags"] = list(tags)
        if isinstance(name, str):
            out["name"] = name
    return out


def normalize_minijupy(meta):
    mj = meta.get("minijupy") if isinstance(meta, dict) else None
    if not isinstance(mj, dict):
        mj = {}
    version = mj.get("version", 1)
    if not is_int_version(version):
        raise MiniJupyError("invalid version")
    result = {"version": version}
    formats = mj.get("formats")
    if formats is not None:
        if formats not in {FORMATS, "py:percent,ipynb"}:
            raise MiniJupyError("invalid formats")
        result["formats"] = formats
    return result


def normalize_notebook(data):
    if not isinstance(data, dict):
        raise MiniJupyError("notebook must be a JSON object")
    if data.get("nbformat") != 4:
        raise MiniJupyError("unsupported notebook nbformat")
    top_meta = data.get("metadata") or {}
    if not isinstance(top_meta, dict):
        top_meta = {}
    cells_in = data.get("cells", [])
    if not isinstance(cells_in, list):
        raise MiniJupyError("invalid notebook cells")

    model = {
        "nbformat": 4,
        "nbformat_minor": data.get("nbformat_minor", 5),
        "metadata": {
            "kernelspec": copy.deepcopy(top_meta.get("kernelspec") if isinstance(top_meta.get("kernelspec"), dict) else {}),
            "language_info": copy.deepcopy(top_meta.get("language_info") if isinstance(top_meta.get("language_info"), dict) else {}),
            "minijupy": normalize_minijupy(top_meta),
        },
        "cells": [],
    }
    if not is_int_version(model["metadata"]["minijupy"]["version"]):
        raise MiniJupyError("invalid version")
    if not isinstance(model["nbformat_minor"], int) or isinstance(model["nbformat_minor"], bool):
        model["nbformat_minor"] = 5

    seen = set()
    for index, cell in enumerate(cells_in, 1):
        if not isinstance(cell, dict):
            raise MiniJupyError("invalid cell")
        cell_type = cell.get("cell_type")
        if cell_type not in {"code", "markdown", "raw"}:
            raise MiniJupyError("unsupported cell type")
        cell_id = cell.get("id", f"c{index}")
        if not isinstance(cell_id, str) or not cell_id:
            raise MiniJupyError("invalid cell id")
        if cell_id in seen:
            raise MiniJupyError("duplicate cell ids")
        seen.add(cell_id)
        out_cell = {
            "id": cell_id,
            "cell_type": cell_type,
            "source": normalize_source(cell.get("source", "")),
            "metadata": normalize_metadata(cell.get("metadata", {})),
        }
        if cell_type == "code":
            out_cell["execution_count"] = cell.get("execution_count")
            outputs = cell.get("outputs", [])
            out_cell["outputs"] = copy.deepcopy(outputs if isinstance(outputs, list) else [])
        model["cells"].append(out_cell)
    return model


def read_ipynb(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed JSON notebook: {exc}")
    return normalize_notebook(data)


def parse_scalar(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_header(lines):
    meta = {"minijupy": {"version": 1}, "kernelspec": {}, "language_info": {}}
    start = 0
    if not lines or lines[0].strip() != "# ---":
        return meta, 0
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "# ---":
            end = i
            break
    if end is None:
        return meta, 0
    section = None
    for raw in lines[1:end]:
        if not raw.startswith("#"):
            continue
        text = raw[1:]
        if text.startswith(" "):
            text = text[1:]
        text = text.rstrip("\r\n")
        if not text.strip():
            continue
        top = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):\s*", text)
        child = re.fullmatch(r"\s{2}([A-Za-z_][A-Za-z0-9_]*):\s*(.*)", text)
        if top:
            section = top.group(1)
        elif child and section == "minijupy":
            key, value = child.group(1), parse_scalar(child.group(2))
            if key == "formats":
                if value not in {FORMATS, "py:percent,ipynb"}:
                    raise MiniJupyError("invalid formats")
                meta["minijupy"]["formats"] = value
            elif key == "version":
                if not is_int_version(value):
                    raise MiniJupyError("invalid version")
                meta["minijupy"]["version"] = value
        elif child and section == "kernelspec":
            key, value = child.group(1), parse_scalar(child.group(2))
            if key == "name" and isinstance(value, str):
                meta["kernelspec"]["name"] = value
    return meta, end + 1


def parse_marker(line):
    if not line.startswith("# %%"):
        return None
    rest = line[4:].strip()
    cell_type = "code"
    if rest.startswith("["):
        close = rest.find("]")
        if close == -1:
            raise MiniJupyError("malformed percent marker")
        bracket = rest[1:close].strip()
        if bracket in {"markdown", "md"}:
            cell_type = "markdown"
        elif bracket == "raw":
            cell_type = "raw"
        else:
            raise MiniJupyError("unsupported percent cell type")
        rest = rest[close + 1:].strip()
    attrs = {}
    if rest:
        try:
            attrs = json.loads(rest)
        except json.JSONDecodeError as exc:
            raise MiniJupyError(f"malformed percent marker JSON: {exc}")
        if not isinstance(attrs, dict):
            raise MiniJupyError("malformed percent marker JSON")
        for key in attrs:
            if key not in {"id", "tags", "name"}:
                raise MiniJupyError("unsupported percent marker metadata")
        if "id" in attrs and not isinstance(attrs["id"], str):
            raise MiniJupyError("invalid cell id")
        if "tags" in attrs and (not isinstance(attrs["tags"], list) or not all(isinstance(x, str) for x in attrs["tags"])):
            raise MiniJupyError("invalid tags")
        if "name" in attrs and not isinstance(attrs["name"], str):
            raise MiniJupyError("invalid name")
    return cell_type, attrs


def parse_markdown_body(text):
    parts = text.splitlines(True)
    out = []
    for line in parts:
        if line.startswith("# "):
            out.append(line[2:])
        else:
            out.append(line)
    return "".join(out)


def read_py(path):
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines(True)
    meta, start = parse_header(lines)
    cells = []
    current = None
    body = []

    def finish():
        nonlocal current, body
        if current is None:
            return
        cell_type, attrs = current
        source = "".join(body)
        if cell_type == "markdown":
            source = parse_markdown_body(source)
        cell = {
            "cell_type": cell_type,
            "source": source,
            "metadata": {},
        }
        if "id" in attrs:
            cell["id"] = attrs["id"]
        if "tags" in attrs:
            cell["metadata"]["tags"] = attrs["tags"]
        if "name" in attrs:
            cell["metadata"]["name"] = attrs["name"]
        if cell_type == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        cells.append(cell)
        current = None
        body = []

    pre = []
    for line in lines[start:]:
        marker = parse_marker(line.rstrip("\n").rstrip("\r"))
        if marker is not None:
            if current is None and pre:
                if any(x.strip() for x in pre):
                    current = ("code", {})
                    body = pre
                    finish()
                pre = []
            finish()
            current = marker
            body = []
        else:
            if current is None:
                pre.append(line)
            else:
                body.append(line)
    if current is None and pre and any(x.strip() for x in pre):
        current = ("code", {})
        body = pre
    finish()

    data = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": meta,
        "cells": cells,
    }
    return normalize_notebook(data)


def read_model(path):
    suffix = Path(path).suffix
    if suffix == ".ipynb":
        return read_ipynb(path)
    if suffix == ".py":
        return read_py(path)
    raise MiniJupyError("unsupported file extension")


def format_of(path):
    return "ipynb" if Path(path).suffix == ".ipynb" else "py:percent"


def write_ipynb_text(model):
    return json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def marker_for_cell(cell):
    kind = ""
    if cell["cell_type"] == "markdown":
        kind = " [markdown]"
    elif cell["cell_type"] == "raw":
        kind = " [raw]"
    attrs = {}
    if cell.get("id"):
        attrs["id"] = cell["id"]
    md = cell.get("metadata", {})
    if "tags" in md:
        attrs["tags"] = md["tags"]
    if "name" in md:
        attrs["name"] = md["name"]
    attr_text = " " + json.dumps(attrs, sort_keys=True, separators=(",", ":")) if attrs else ""
    return f"# %%{kind}{attr_text}\n"


def write_markdown_source(source):
    if source == "":
        return ""
    return "".join("# " + line for line in source.splitlines(True))


def write_py_text(model):
    mj = model["metadata"]["minijupy"]
    lines = ["# ---\n", "# minijupy:\n"]
    if "formats" in mj:
        lines.append(f"#   formats: {mj['formats']}\n")
    lines.append(f"#   version: {mj['version']}\n")
    kernelspec = model["metadata"].get("kernelspec") or {}
    if isinstance(kernelspec.get("name"), str):
        lines.extend(["# kernelspec:\n", f"#   name: {kernelspec['name']}\n"])
    lines.append("# ---\n")
    for index, cell in enumerate(model["cells"]):
        lines.append(marker_for_cell(cell))
        if cell["cell_type"] == "markdown":
            lines.append(write_markdown_source(cell.get("source", "")))
        else:
            lines.append(cell.get("source", ""))
        if index != len(model["cells"]) - 1 and lines and lines[-1] and not lines[-1].endswith("\n"):
            lines.append("\n")
    return "".join(lines)


def set_formats(model):
    new = copy.deepcopy(model)
    new["metadata"]["minijupy"]["formats"] = FORMATS
    return new


def model_version(model):
    return model["metadata"]["minijupy"].get("version", 1)


def comparable_model(model, include_outputs=False):
    m = copy.deepcopy(model)
    for cell in m["cells"]:
        if cell["cell_type"] == "code" and not include_outputs:
            cell.pop("execution_count", None)
            cell.pop("outputs", None)
    return m


def compare_models(a, b):
    differences = []
    if len(a["cells"]) != len(b["cells"]):
        differences.append("cell_count")
    if a["metadata"]["minijupy"].get("formats") != b["metadata"]["minijupy"].get("formats"):
        differences.append("formats")
    if model_version(a) != model_version(b):
        differences.append("version")
    for ca, cb in zip(a["cells"], b["cells"]):
        if ca["cell_type"] != cb["cell_type"] and "cell_type" not in differences:
            differences.append("cell_type")
        if ca.get("source", "") != cb.get("source", "") and "source" not in differences:
            differences.append("source")
        if ca.get("id") != cb.get("id") and "id" not in differences:
            differences.append("id")
        if ca.get("metadata", {}).get("tags") != cb.get("metadata", {}).get("tags") and "tags" not in differences:
            differences.append("tags")
        if ca.get("metadata", {}).get("name") != cb.get("metadata", {}).get("name") and "name" not in differences:
            differences.append("name")
    return differences


def source_hash(cell):
    return hashlib.sha256((cell["cell_type"] + "\0" + cell.get("source", "")).encode("utf-8")).hexdigest()


def preserve_outputs(new_model, old_model):
    old_code = []
    by_id = {}
    for idx, cell in enumerate(old_model["cells"]):
        if cell["cell_type"] == "code":
            old_code.append((idx, cell))
            by_id[cell.get("id")] = (idx, cell)
    used = set()
    result = copy.deepcopy(new_model)
    for idx, cell in enumerate(result["cells"]):
        if cell["cell_type"] != "code":
            cell.pop("execution_count", None)
            cell.pop("outputs", None)
            continue
        match = None
        cid = cell.get("id")
        if cid in by_id and by_id[cid][0] not in used:
            match = by_id[cid]
        if match is None:
            wanted = source_hash(cell)
            for old_idx, old in old_code:
                if old_idx not in used and source_hash(old) == wanted:
                    match = (old_idx, old)
                    break
        if match is None and idx < len(old_model["cells"]):
            old = old_model["cells"][idx]
            if old["cell_type"] == "code":
                old_idx = idx
                if old_idx not in used:
                    match = (old_idx, old)
        if match is not None:
            used.add(match[0])
            cell["execution_count"] = copy.deepcopy(match[1].get("execution_count"))
            cell["outputs"] = copy.deepcopy(match[1].get("outputs", []))
        else:
            cell["execution_count"] = None
            cell["outputs"] = []
    return result


def state_entry(pair, ipynb_model, text_model):
    return {
        "ipynb": pair["ipynb"],
        "text": pair["text"],
        "last_synced": {
            "ipynb_version": model_version(ipynb_model),
            "text_version": model_version(text_model),
            "ipynb_hash": hash_model(ipynb_model),
            "text_hash": hash_model(text_model),
        },
    }


def rel_root(cfg):
    try:
        return Path(cfg["root"]).resolve().relative_to(Path.cwd().resolve()).as_posix() or "."
    except ValueError:
        return Path(cfg["root"]).as_posix()


def load_pair_models(pair, cfg):
    ipath, tpath = abs_pair(pair, cfg)
    exists = {"ipynb": ipath.exists(), "text": tpath.exists()}
    models = {"ipynb": None, "text": None}
    errors = []
    if exists["ipynb"]:
        try:
            models["ipynb"] = read_ipynb(ipath)
        except MiniJupyError as exc:
            errors.append(str(exc))
    if exists["text"]:
        try:
            models["text"] = read_py(tpath)
        except MiniJupyError as exc:
            errors.append(str(exc))
    return exists, models, errors


def determine_source(pair, exists, models, state, explicit=None):
    entry = state["pairs"].get(pair["key"])
    if explicit:
        return explicit, False, None
    if not exists["ipynb"] and not exists["text"]:
        return "none", False, "both sides are missing"
    if exists["ipynb"] and not exists["text"]:
        return "ipynb", False, None
    if exists["text"] and not exists["ipynb"]:
        return "text", False, None
    if not entry:
        return "none", False, "pair has no state; run pair or pass --source"
    last = entry.get("last_synced", {}) if isinstance(entry, dict) else {}
    last_i = last.get("ipynb_version")
    last_t = last.get("text_version")
    cur_i = model_version(models["ipynb"])
    cur_t = model_version(models["text"])
    ipynb_changed = isinstance(last_i, int) and cur_i > last_i
    text_changed = isinstance(last_t, int) and cur_t > last_t
    if ipynb_changed and text_changed:
        return "none", True, None
    if ipynb_changed:
        return "ipynb", False, None
    if text_changed:
        return "text", False, None
    return "none", False, None


def pair_status(pair, cfg, state, command="status", explicit_source=None):
    exists, models, errors = load_pair_models(pair, cfg)
    source = "none"
    conflict = False
    source_error = None
    if not errors:
        source, conflict, source_error = determine_source(pair, exists, models, state, explicit_source)
    entry = state["pairs"].get(pair["key"], {})
    last = entry.get("last_synced", {}) if isinstance(entry, dict) else {}
    versions = {
        "ipynb": model_version(models["ipynb"]) if models["ipynb"] else None,
        "text": model_version(models["text"]) if models["text"] else None,
        "last_ipynb": last.get("ipynb_version"),
        "last_text": last.get("text_version"),
    }
    missing = []
    if not exists["ipynb"]:
        missing.append(pair["ipynb"])
    if not exists["text"]:
        missing.append(pair["text"])
    if source_error and command == "sync":
        errors.append(source_error)
    if conflict:
        source = "none"

    planned = []
    if not errors and not conflict:
        if source == "ipynb":
            planned = [pair["text"], STATE_NAME]
        elif source == "text":
            planned = [pair["ipynb"], STATE_NAME]
    differences = []
    roundtrip_ok = False
    if not errors and exists["ipynb"] and exists["text"]:
        differences = compare_models(comparable_model(models["ipynb"]), comparable_model(models["text"]))
        roundtrip_ok = not differences
        if isinstance(last.get("ipynb_version"), int) and versions["ipynb"] is not None and last["ipynb_version"] > versions["ipynb"]:
            differences.append("state")
            roundtrip_ok = False
        if isinstance(last.get("text_version"), int) and versions["text"] is not None and last["text_version"] > versions["text"]:
            if "state" not in differences:
                differences.append("state")
            roundtrip_ok = False
    elif missing:
        roundtrip_ok = False

    return {
        "ipynb": pair["ipynb"],
        "text": pair["text"],
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


def summarize(pairs):
    return {
        "pairs": len(pairs),
        "conflicts": sum(1 for p in pairs if p["conflict"]),
        "missing": sum(len(p["missing"]) for p in pairs),
        "planned_writes": sum(len(p["planned_writes"]) for p in pairs),
        "errors": sum(len(p["errors"]) for p in pairs),
    }


def discover_pairs(cfg, state):
    root = Path(cfg["root"])
    pairs = {}

    def add(path):
        pair = pair_for_path(path, cfg)
        old = pairs.get(pair["key"])
        if old and old != pair:
            raise MiniJupyError("duplicate paired paths")
        pairs[pair["key"]] = pair

    if cfg["notebook_dir"] is None:
        search_roots = [root]
    else:
        search_roots = [root / cfg["notebook_dir"], root / cfg["script_dir"]]
    for sr in search_roots:
        if not sr.exists():
            continue
        for p in sr.rglob("*"):
            if p.is_file() and p.name != STATE_NAME and p.suffix in {".ipynb", ".py"}:
                add(p)
    for key, entry in state.get("pairs", {}).items():
        if isinstance(entry, dict) and isinstance(entry.get("ipynb"), str) and isinstance(entry.get("text"), str):
            pairs.setdefault(key, {"key": key, "ipynb": entry["ipynb"], "text": entry["text"]})
    return [pairs[k] for k in sorted(pairs)]


def command_inspect(args, cfg):
    path = Path(args.input).resolve()
    model = read_model(path)
    return {
        "ok": True,
        "command": "inspect",
        "path": relpath(path, cfg["root"]),
        "format": "ipynb" if path.suffix == ".ipynb" else "py:percent",
        "version": model_version(model),
        "notebook": model,
    }, {}


def command_to_text(args, cfg):
    if Path(args.input).suffix != ".ipynb" or Path(args.output).suffix != ".py":
        raise MiniJupyError("invalid to-text input or output")
    model = read_ipynb(args.input)
    return {"ok": True, "command": "to-text", "input": relpath(args.input, cfg["root"]), "output": relpath(args.output, cfg["root"])}, {
        Path(args.output).resolve(): write_py_text(model)
    }


def command_to_ipynb(args, cfg):
    if Path(args.input).suffix != ".py" or Path(args.output).suffix != ".ipynb":
        raise MiniJupyError("invalid to-ipynb input or output")
    model = read_py(args.input)
    return {"ok": True, "command": "to-ipynb", "input": relpath(args.input, cfg["root"]), "output": relpath(args.output, cfg["root"])}, {
        Path(args.output).resolve(): write_ipynb_text(model)
    }


def command_pair(args, cfg):
    pair = pair_for_path(args.input, cfg)
    ipath, tpath = abs_pair(pair, cfg)
    iexists, texists = ipath.exists(), tpath.exists()
    if not iexists and not texists:
        raise MiniJupyError("both sides are missing")
    if iexists:
        ipynb_model = set_formats(read_ipynb(ipath))
    else:
        ipynb_model = set_formats(read_py(tpath))
    if texists:
        text_model = set_formats(read_py(tpath))
    else:
        text_model = set_formats(ipynb_model)
    state = load_state(cfg)
    state["pairs"][pair["key"]] = state_entry(pair, ipynb_model, text_model)
    writes = {
        ipath: write_ipynb_text(ipynb_model),
        tpath: write_py_text(text_model),
        state_path(cfg): dump_state(state),
    }
    result = {
        "ok": True,
        "command": "pair",
        "ipynb": pair["ipynb"],
        "text": pair["text"],
        "state": STATE_NAME,
    }
    return result, writes


def status_or_check(args, cfg, command):
    state = load_state(cfg)
    if args.all:
        if not args.config:
            raise MiniJupyError("--all requires --config")
        pairs = discover_pairs(cfg, state)
    else:
        pairs = [pair_for_path(args.input, cfg)]
    items = [pair_status(p, cfg, state, command=command) for p in pairs]
    result = {"ok": True, "command": command, "root": rel_root(cfg), "pairs": items, "summary": summarize(items)}
    if any(p["errors"] for p in items):
        result["ok"] = False
    return result, {}


def build_sync_write(pair, cfg, state, explicit_source=None):
    ipath, tpath = abs_pair(pair, cfg)
    exists, models, errors = load_pair_models(pair, cfg)
    if errors:
        raise MiniJupyError("; ".join(errors))
    source, conflict, source_error = determine_source(pair, exists, models, state, explicit_source)
    if conflict:
        raise MiniJupyError("conflict without explicit --source")
    if source_error:
        raise MiniJupyError(source_error)
    if source == "none":
        return {}, pair_status(pair, cfg, state, command="sync", explicit_source=explicit_source)
    status = pair_status(pair, cfg, state, command="sync", explicit_source=explicit_source)
    if source == "ipynb":
        if not exists["ipynb"]:
            raise MiniJupyError("ipynb source is missing")
        ipynb_model = set_formats(models["ipynb"])
        text_model = set_formats(ipynb_model)
        writes = {tpath: write_py_text(text_model)}
    elif source == "text":
        if not exists["text"]:
            raise MiniJupyError("text source is missing")
        text_model = set_formats(models["text"])
        ipynb_model = set_formats(text_model)
        if exists["ipynb"]:
            ipynb_model = preserve_outputs(ipynb_model, models["ipynb"])
        writes = {ipath: write_ipynb_text(ipynb_model)}
    else:
        raise MiniJupyError("invalid source")
    state["pairs"][pair["key"]] = state_entry(pair, ipynb_model, text_model)
    writes[state_path(cfg)] = dump_state(state)
    status["source"] = source
    status["planned_writes"] = [relpath(p, cfg["root"]) if Path(p).resolve() != state_path(cfg).resolve() else STATE_NAME for p in writes]
    return writes, status


def command_sync(args, cfg):
    state = load_state(cfg)
    if args.all:
        if not args.config:
            raise MiniJupyError("--all requires --config")
        pairs = discover_pairs(cfg, state)
    else:
        pairs = [pair_for_path(args.input, cfg)]

    planned_state = copy.deepcopy(state)
    all_writes = {}
    statuses = []
    for pair in pairs:
        writes, status = build_sync_write(pair, cfg, planned_state, args.source)
        for path, data in writes.items():
            all_writes[Path(path).resolve()] = data
        statuses.append(status)
    result = {"ok": True, "command": "sync", "root": rel_root(cfg), "pairs": statuses, "summary": summarize(statuses)}
    return result, all_writes


def build_parser():
    parser = argparse.ArgumentParser(prog="minijupy.py")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_input_config(p):
        p.add_argument("--input")
        p.add_argument("--config")

    p = sub.add_parser("inspect")
    add_input_config(p)
    p = sub.add_parser("to-text")
    add_input_config(p)
    p.add_argument("--output", required=True)
    p = sub.add_parser("to-ipynb")
    add_input_config(p)
    p.add_argument("--output", required=True)
    p = sub.add_parser("pair")
    add_input_config(p)

    for name in ("status", "check"):
        p = sub.add_parser(name)
        p.add_argument("--input")
        p.add_argument("--all", action="store_true")
        p.add_argument("--config")

    p = sub.add_parser("sync")
    p.add_argument("--input")
    p.add_argument("--all", action="store_true")
    p.add_argument("--config")
    p.add_argument("--source", choices=["ipynb", "text"])
    return parser


def validate_args(args):
    if args.command in {"inspect", "to-text", "to-ipynb", "pair"} and not args.input:
        raise MiniJupyError("--input is required")
    if args.command in {"status", "check", "sync"}:
        if bool(args.input) == bool(args.all):
            raise MiniJupyError("supply exactly one of --input or --all")


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        validate_args(args)
        cfg = load_config(getattr(args, "config", None))
        if args.command == "inspect":
            result, writes = command_inspect(args, cfg)
        elif args.command == "to-text":
            result, writes = command_to_text(args, cfg)
        elif args.command == "to-ipynb":
            result, writes = command_to_ipynb(args, cfg)
        elif args.command == "pair":
            result, writes = command_pair(args, cfg)
        elif args.command == "status":
            result, writes = status_or_check(args, cfg, "status")
        elif args.command == "check":
            result, writes = status_or_check(args, cfg, "check")
        elif args.command == "sync":
            result, writes = command_sync(args, cfg)
        else:
            raise MiniJupyError("unsupported command")
        if writes:
            atomic_write_many(writes)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0 if result.get("ok", True) else 1
    except MiniJupyError as exc:
        return fail(str(exc))
    except OSError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())

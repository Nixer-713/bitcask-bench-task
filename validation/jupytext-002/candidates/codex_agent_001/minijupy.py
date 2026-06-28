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
VALID_FORMATS = {FORMATS, "py:percent,ipynb"}
VALID_CELL_TYPES = {"code", "markdown", "raw"}


class MiniJupyError(Exception):
    pass


def relpath(path, root):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), root.resolve()).replace(os.sep, "/")


def stable_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(model):
    return hashlib.sha256(stable_json(model).encode("utf-8")).hexdigest()


def normalize_source(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(str(part) for part in value)
    return str(value)


def parse_version(value, where):
    if value is None:
        return 1
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MiniJupyError(f"invalid version in {where}")
    return value


def clean_cell_metadata(metadata):
    out = {}
    if isinstance(metadata, dict):
        tags = metadata.get("tags")
        if isinstance(tags, list) and all(isinstance(t, str) for t in tags):
            out["tags"] = list(tags)
        name = metadata.get("name")
        if isinstance(name, str):
            out["name"] = name
    return out


def normalize_notebook(raw, source_name="<notebook>"):
    if not isinstance(raw, dict):
        raise MiniJupyError(f"malformed notebook: {source_name}")
    if raw.get("nbformat") != 4:
        raise MiniJupyError("unsupported notebook nbformat")

    raw_meta = raw.get("metadata") or {}
    if not isinstance(raw_meta, dict):
        raw_meta = {}
    raw_mj = raw_meta.get("minijupy") or {}
    if not isinstance(raw_mj, dict):
        raw_mj = {}
    version = parse_version(raw_mj.get("version"), "notebook metadata")
    formats = raw_mj.get("formats")
    if formats is not None and formats not in VALID_FORMATS:
        raise MiniJupyError("invalid minijupy formats")

    metadata = {
        "kernelspec": raw_meta.get("kernelspec") if isinstance(raw_meta.get("kernelspec"), dict) else {},
        "language_info": raw_meta.get("language_info") if isinstance(raw_meta.get("language_info"), dict) else {},
        "minijupy": {"version": version},
    }
    if formats is not None:
        metadata["minijupy"]["formats"] = formats

    seen_ids = set()
    cells = []
    for index, raw_cell in enumerate(raw.get("cells") or [], start=1):
        if not isinstance(raw_cell, dict):
            raise MiniJupyError("malformed notebook cell")
        cell_type = raw_cell.get("cell_type")
        if cell_type not in VALID_CELL_TYPES:
            raise MiniJupyError(f"unsupported cell type: {cell_type}")
        cell_id = raw_cell.get("id") or f"c{index}"
        if not isinstance(cell_id, str):
            raise MiniJupyError("invalid cell id")
        if cell_id in seen_ids:
            raise MiniJupyError("duplicate cell ids")
        seen_ids.add(cell_id)
        cell = {
            "id": cell_id,
            "cell_type": cell_type,
            "source": normalize_source(raw_cell.get("source", "")),
            "metadata": clean_cell_metadata(raw_cell.get("metadata") or {}),
        }
        if cell_type == "code":
            cell["execution_count"] = raw_cell.get("execution_count")
            cell["outputs"] = raw_cell.get("outputs") if isinstance(raw_cell.get("outputs"), list) else []
        cells.append(cell)

    return {
        "nbformat": 4,
        "nbformat_minor": raw.get("nbformat_minor", 5),
        "metadata": metadata,
        "cells": cells,
    }


def read_ipynb(path):
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed JSON notebook: {exc}") from exc
    except OSError as exc:
        raise MiniJupyError(str(exc)) from exc
    return normalize_notebook(raw, path.as_posix())


def parse_header(lines):
    if not lines or lines[0].rstrip("\n") != "# ---":
        return {}, 0
    collected = []
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].rstrip("\n") == "# ---":
            end = idx
            break
        line = lines[idx]
        if line.startswith("# "):
            collected.append(line[2:].rstrip("\n"))
        elif line.startswith("#"):
            collected.append(line[1:].rstrip("\n"))
        else:
            collected.append(line.rstrip("\n"))
    if end is None:
        return {}, 0

    header = {}
    section = None
    for raw in collected:
        if not raw.strip():
            continue
        if not raw.startswith(" ") and raw.endswith(":"):
            section = raw[:-1].strip()
            continue
        m = re.match(r"\s{2}([A-Za-z0-9_]+):\s*(.*)\s*$", raw)
        if section and m:
            header[f"{section}.{m.group(1)}"] = m.group(2).strip().strip('"')
    return header, end + 1


def parse_marker(line):
    rest = line[4:].strip()
    cell_type = "code"
    meta = {}
    if rest.startswith("["):
        close = rest.find("]")
        if close < 0:
            raise MiniJupyError("malformed percent marker")
        marker_type = rest[1:close].strip()
        if marker_type == "md":
            marker_type = "markdown"
        if marker_type not in {"markdown", "raw"}:
            raise MiniJupyError(f"unsupported percent cell type: {marker_type}")
        cell_type = marker_type
        rest = rest[close + 1 :].strip()
    if rest:
        try:
            parsed = json.loads(rest)
        except json.JSONDecodeError as exc:
            raise MiniJupyError(f"malformed percent marker JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise MiniJupyError("marker JSON must be an object")
        unknown = set(parsed) - {"id", "tags", "name"}
        if unknown:
            raise MiniJupyError("unsupported marker metadata")
        if "id" in parsed:
            if not isinstance(parsed["id"], str):
                raise MiniJupyError("invalid marker id")
            meta["id"] = parsed["id"]
        if "tags" in parsed:
            if not isinstance(parsed["tags"], list) or not all(isinstance(t, str) for t in parsed["tags"]):
                raise MiniJupyError("invalid marker tags")
            meta["tags"] = list(parsed["tags"])
        if "name" in parsed:
            if not isinstance(parsed["name"], str):
                raise MiniJupyError("invalid marker name")
            meta["name"] = parsed["name"]
    return cell_type, meta


def markdown_from_percent(lines):
    out = []
    for line in lines:
        if line.startswith("# "):
            out.append(line[2:])
        else:
            out.append(line)
    return "".join(out)


def make_text_model(cells, version, formats=None, kernelspec_name=None):
    metadata = {
        "kernelspec": {},
        "language_info": {},
        "minijupy": {"version": version},
    }
    if kernelspec_name:
        metadata["kernelspec"]["name"] = kernelspec_name
    if formats is not None:
        metadata["minijupy"]["formats"] = formats
    seen = set()
    normalized_cells = []
    for idx, cell in enumerate(cells, start=1):
        cell_id = cell.get("id") or f"c{idx}"
        if cell_id in seen:
            raise MiniJupyError("duplicate cell ids")
        seen.add(cell_id)
        item = {
            "id": cell_id,
            "cell_type": cell["cell_type"],
            "source": cell.get("source", ""),
            "metadata": clean_cell_metadata(cell.get("metadata", {})),
        }
        if item["cell_type"] == "code":
            item["execution_count"] = None
            item["outputs"] = []
        normalized_cells.append(item)
    return {"nbformat": 4, "nbformat_minor": 5, "metadata": metadata, "cells": normalized_cells}


def read_text(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines(True)
    except OSError as exc:
        raise MiniJupyError(str(exc)) from exc
    header, start = parse_header(lines)
    version_raw = header.get("minijupy.version")
    version = 1
    if version_raw is not None:
        try:
            version = int(version_raw)
        except ValueError as exc:
            raise MiniJupyError("invalid version in text header") from exc
        if version < 0:
            raise MiniJupyError("invalid version in text header")
    formats = header.get("minijupy.formats")
    if formats is not None and formats not in VALID_FORMATS:
        raise MiniJupyError("invalid minijupy formats")
    kernelspec_name = header.get("kernelspec.name")

    cells = []
    body = []
    current = None

    def finish():
        nonlocal body, current
        if current is None:
            return
        source = markdown_from_percent(body) if current["cell_type"] == "markdown" else "".join(body)
        cells.append({
            "cell_type": current["cell_type"],
            "source": source,
            "id": current.get("id"),
            "metadata": {k: current[k] for k in ("tags", "name") if k in current},
        })
        body = []

    prefix = []
    for line in lines[start:]:
        if line.startswith("# %%"):
            if current is None and prefix:
                if any(part.strip() for part in prefix):
                    cells.append({"cell_type": "code", "source": "".join(prefix), "metadata": {}})
                prefix = []
            finish()
            cell_type, meta = parse_marker(line)
            current = {"cell_type": cell_type, **meta}
        else:
            if current is None:
                prefix.append(line)
            else:
                body.append(line)
    if current is None:
        if any(part.strip() for part in prefix):
            cells.append({"cell_type": "code", "source": "".join(prefix), "metadata": {}})
    else:
        finish()
    return make_text_model(cells, version, formats, kernelspec_name)


def notebook_version(model):
    return model["metadata"]["minijupy"].get("version", 1)


def force_formats(model):
    updated = copy.deepcopy(model)
    updated["metadata"].setdefault("minijupy", {})["formats"] = FORMATS
    return updated


def has_pair_formats(model):
    return model["metadata"].get("minijupy", {}).get("formats") == FORMATS


def write_ipynb_text(model):
    return json.dumps(model, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def marker_for_cell(cell):
    if cell["cell_type"] == "code":
        marker = "# %%"
    elif cell["cell_type"] == "markdown":
        marker = "# %% [markdown]"
    else:
        marker = "# %% [raw]"
    meta = {}
    if cell.get("id"):
        meta["id"] = cell["id"]
    tags = cell.get("metadata", {}).get("tags")
    if tags:
        meta["tags"] = tags
    name = cell.get("metadata", {}).get("name")
    if name:
        meta["name"] = name
    if meta:
        marker += " " + json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    return marker + "\n"


def markdown_to_percent(source):
    return "".join("# " + line for line in source.splitlines(True))


def write_text_script(model):
    mj = model["metadata"]["minijupy"]
    lines = ["# ---\n", "# minijupy:\n"]
    if "formats" in mj:
        lines.append(f"#   formats: {mj['formats']}\n")
    lines.append(f"#   version: {notebook_version(model)}\n")
    kernel_name = model["metadata"].get("kernelspec", {}).get("name")
    if kernel_name:
        lines.extend(["# kernelspec:\n", f"#   name: {kernel_name}\n"])
    lines.append("# ---\n")
    for index, cell in enumerate(model["cells"]):
        if index or lines[-1] != "# ---\n":
            pass
        lines.append(marker_for_cell(cell))
        if cell["cell_type"] == "markdown":
            lines.append(markdown_to_percent(cell.get("source", "")))
        else:
            lines.append(cell.get("source", ""))
    return "".join(lines)


def read_model(path):
    if path.suffix == ".ipynb":
        return read_ipynb(path), "ipynb"
    if path.suffix == ".py":
        return read_text(path), "text"
    raise MiniJupyError("unsupported file type")


class Config:
    def __init__(self, path=None):
        self.path = Path(path).resolve() if path else None
        self.root = self.path.parent if self.path else Path.cwd().resolve()
        self.formats = FORMATS
        self.notebook_dir = None
        self.script_dir = None
        if self.path:
            self._load()

    def _load(self):
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise MiniJupyError(str(exc)) from exc
        values = {}
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = re.match(r'([A-Za-z_]+)\s*=\s*"([^"]*)"\s*$', stripped)
            if not m:
                raise MiniJupyError("invalid config")
            key, value = m.groups()
            if key not in {"formats", "notebook_dir", "script_dir"}:
                raise MiniJupyError("invalid config key")
            values[key] = value
        formats = values.get("formats")
        if formats is not None and formats not in VALID_FORMATS:
            raise MiniJupyError("invalid config formats")
        if ("notebook_dir" in values) != ("script_dir" in values):
            raise MiniJupyError("invalid config directories")
        self.formats = formats or FORMATS
        self.notebook_dir = values.get("notebook_dir")
        self.script_dir = values.get("script_dir")

    def state_path(self):
        return self.root / STATE_NAME

    def rel(self, path):
        return relpath(path, self.root)

    def full(self, rel):
        return self.root / rel


def load_state(config):
    path = config.state_path()
    if not path.exists():
        return {"pairs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MiniJupyError(f"malformed state file: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("pairs", {}), dict):
        raise MiniJupyError("malformed state file")
    data.setdefault("pairs", {})
    return data


def pair_paths(input_path, config):
    path = Path(input_path).resolve()
    suffix = path.suffix
    if suffix not in {".ipynb", ".py"}:
        raise MiniJupyError("unsupported file type")
    rel = config.rel(path)
    if config.notebook_dir and config.script_dir:
        nb_parts = Path(config.notebook_dir.strip("/")).parts
        py_parts = Path(config.script_dir.strip("/")).parts
        parts = Path(rel).parts
        if suffix == ".ipynb" and parts[: len(nb_parts)] == nb_parts:
            inner = Path(*parts[len(nb_parts) :]).with_suffix(".py").as_posix()
            ipynb = rel
            text = (Path(*py_parts) / inner).as_posix()
        elif suffix == ".py" and parts[: len(py_parts)] == py_parts:
            inner = Path(*parts[len(py_parts) :]).with_suffix(".ipynb").as_posix()
            text = rel
            ipynb = (Path(*nb_parts) / inner).as_posix()
        else:
            raise MiniJupyError("path mismatch")
    else:
        base = Path(rel)
        ipynb = base.with_suffix(".ipynb").as_posix()
        text = base.with_suffix(".py").as_posix()
    return ipynb, text


def pair_key(ipynb_rel):
    return ipynb_rel


def state_entry_for(ipynb_rel, text_rel, ipynb_model, text_model):
    return {
        "ipynb": ipynb_rel,
        "text": text_rel,
        "last_synced": {
            "ipynb_version": notebook_version(ipynb_model),
            "text_version": notebook_version(text_model),
            "ipynb_hash": stable_hash(ipynb_model),
            "text_hash": stable_hash(text_model),
        },
    }


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def apply_writes(writes):
    for path, content in writes:
        atomic_write(path, content)


def compare_models(ipynb_model, text_model, include_outputs=False):
    diffs = []
    if notebook_version(ipynb_model) != notebook_version(text_model):
        diffs.append("version")
    if ipynb_model["metadata"]["minijupy"].get("formats") != text_model["metadata"]["minijupy"].get("formats"):
        diffs.append("formats")
    a_cells = ipynb_model["cells"]
    b_cells = text_model["cells"]
    if len(a_cells) != len(b_cells):
        diffs.append("cell_count")
    for a, b in zip(a_cells, b_cells):
        if a.get("cell_type") != b.get("cell_type") and "cell_type" not in diffs:
            diffs.append("cell_type")
        if a.get("source") != b.get("source") and "source" not in diffs:
            diffs.append("source")
        if a.get("id") != b.get("id") and "id" not in diffs:
            diffs.append("id")
        if a.get("metadata", {}).get("tags", []) != b.get("metadata", {}).get("tags", []) and "tags" not in diffs:
            diffs.append("tags")
        if a.get("metadata", {}).get("name") != b.get("metadata", {}).get("name") and "name" not in diffs:
            diffs.append("name")
        if include_outputs and a.get("cell_type") == "code":
            if a.get("execution_count") != b.get("execution_count") or a.get("outputs", []) != b.get("outputs", []):
                if "outputs" not in diffs:
                    diffs.append("outputs")
    return diffs


def source_hash_key(cell):
    return hashlib.sha256((cell.get("cell_type", "") + "\0" + cell.get("source", "")).encode("utf-8")).hexdigest()


def preserve_outputs(new_model, old_ipynb):
    result = copy.deepcopy(new_model)
    old_cells = old_ipynb["cells"]
    used = set()
    by_id = {cell.get("id"): idx for idx, cell in enumerate(old_cells) if cell.get("id")}
    for pos, cell in enumerate(result["cells"]):
        if cell["cell_type"] != "code":
            continue
        match = None
        old_id = by_id.get(cell.get("id"))
        if old_id is not None and old_id not in used:
            match = old_id
        if match is None:
            key = source_hash_key(cell)
            for idx, old in enumerate(old_cells):
                if idx not in used and old.get("cell_type") == cell["cell_type"] and source_hash_key(old) == key:
                    match = idx
                    break
        if match is None and pos < len(old_cells) and pos not in used and old_cells[pos].get("cell_type") == cell["cell_type"]:
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


def status_for_pair(ipynb_rel, text_rel, config, state, command="status", explicit_source=None):
    ipynb_path = config.full(ipynb_rel)
    text_path = config.full(text_rel)
    exists = {"ipynb": ipynb_path.exists(), "text": text_path.exists()}
    errors = []
    missing = [name for name, present in exists.items() if not present]
    ipynb_model = text_model = None
    ipynb_version = text_version = None
    diffs = []

    try:
        if exists["ipynb"]:
            ipynb_model = read_ipynb(ipynb_path)
            ipynb_version = notebook_version(ipynb_model)
        if exists["text"]:
            text_model = read_text(text_path)
            text_version = notebook_version(text_model)
    except MiniJupyError as exc:
        errors.append(str(exc))

    entry = state.get("pairs", {}).get(pair_key(ipynb_rel), {})
    last = entry.get("last_synced", {}) if isinstance(entry, dict) else {}
    last_ipynb = last.get("ipynb_version")
    last_text = last.get("text_version")
    conflict = False
    source = "none"

    if not errors:
        if explicit_source in {"ipynb", "text"}:
            source = explicit_source
        elif exists["ipynb"] and not exists["text"]:
            source = "ipynb"
        elif exists["text"] and not exists["ipynb"]:
            source = "text"
        elif exists["ipynb"] and exists["text"] and entry:
            ip_changed = isinstance(last_ipynb, int) and ipynb_version is not None and ipynb_version > last_ipynb
            text_changed = isinstance(last_text, int) and text_version is not None and text_version > last_text
            if ip_changed and text_changed:
                conflict = True
                source = "none"
            elif ip_changed:
                source = "ipynb"
            elif text_changed:
                source = "text"
        elif exists["ipynb"] and exists["text"] and not entry:
            source = "none"

    planned = []
    if not errors and not conflict:
        if source == "ipynb":
            planned = [text_rel]
            if ipynb_model is not None and not has_pair_formats(ipynb_model):
                planned.append(ipynb_rel)
            planned.append(STATE_NAME)
        elif source == "text":
            planned = [ipynb_rel]
            if text_model is not None and not has_pair_formats(text_model):
                planned.append(text_rel)
            planned.append(STATE_NAME)
    if source == "none":
        planned = []

    roundtrip_ok = not errors and not missing
    if roundtrip_ok and ipynb_model and text_model:
        diffs = compare_models(ipynb_model, text_model, include_outputs=(command == "check"))
        if diffs:
            roundtrip_ok = False
    if command == "check" and not errors:
        if isinstance(last_ipynb, int) and ipynb_version is not None and last_ipynb > ipynb_version:
            diffs.append("state")
        if isinstance(last_text, int) and text_version is not None and last_text > text_version:
            diffs.append("state")
        if "state" in diffs:
            roundtrip_ok = False

    return {
        "ipynb": ipynb_rel,
        "text": text_rel,
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
        "differences": list(dict.fromkeys(diffs)),
        "errors": errors,
        "_models": {"ipynb": ipynb_model, "text": text_model},
    }


def public_pair(pair):
    return {k: v for k, v in pair.items() if not k.startswith("_")}


def summarize(pairs):
    return {
        "pairs": len(pairs),
        "conflicts": sum(1 for p in pairs if p["conflict"]),
        "missing": sum(len(p["missing"]) for p in pairs),
        "planned_writes": sum(len(p["planned_writes"]) for p in pairs),
        "errors": sum(len(p["errors"]) for p in pairs),
    }


def discover_pairs(config, state):
    pairs = {}
    def add(path):
        try:
            ipynb, text = pair_paths(path, config)
        except MiniJupyError:
            return
        old = pairs.get(ipynb)
        if old and old != text:
            raise MiniJupyError("duplicate paired paths")
        pairs[ipynb] = text

    if config.notebook_dir and config.script_dir:
        roots = [config.root / config.notebook_dir, config.root / config.script_dir]
    else:
        roots = [config.root]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".ipynb", ".py"} and path.name != Path(__file__).name:
                add(path)
    for key, entry in state.get("pairs", {}).items():
        if isinstance(entry, dict) and "ipynb" in entry and "text" in entry:
            pairs.setdefault(entry["ipynb"], entry["text"])
        else:
            pairs.setdefault(key, str(Path(key).with_suffix(".py")))
    return sorted(pairs.items())


def cmd_inspect(args):
    config = Config(args.config)
    path = Path(args.input).resolve()
    model, fmt = read_model(path)
    return {
        "ok": True,
        "command": "inspect",
        "path": config.rel(path),
        "format": fmt,
        "version": notebook_version(model),
        "notebook": model,
    }, []


def cmd_to_text(args):
    if Path(args.input).suffix != ".ipynb" or Path(args.output).suffix != ".py":
        raise MiniJupyError("invalid to-text input or output")
    model = read_ipynb(Path(args.input))
    output = Path(args.output)
    return {
        "ok": True,
        "command": "to-text",
        "input": args.input,
        "output": args.output,
    }, [(output, write_text_script(model))]


def cmd_to_ipynb(args):
    if Path(args.input).suffix != ".py" or Path(args.output).suffix != ".ipynb":
        raise MiniJupyError("invalid to-ipynb input or output")
    model = read_text(Path(args.input))
    output = Path(args.output)
    return {
        "ok": True,
        "command": "to-ipynb",
        "input": args.input,
        "output": args.output,
    }, [(output, write_ipynb_text(model))]


def cmd_pair(args):
    config = Config(args.config)
    state = load_state(config)
    ipynb_rel, text_rel = pair_paths(args.input, config)
    ipynb_path = config.full(ipynb_rel)
    text_path = config.full(text_rel)
    exists_ipynb = ipynb_path.exists()
    exists_text = text_path.exists()
    if not exists_ipynb and not exists_text:
        raise MiniJupyError("both sides are missing")

    writes = []
    if exists_ipynb:
        ipynb_model = force_formats(read_ipynb(ipynb_path))
    else:
        text_model = force_formats(read_text(text_path))
        ipynb_model = text_model
        writes.append((ipynb_path, write_ipynb_text(ipynb_model)))
    if exists_text:
        text_model = force_formats(read_text(text_path))
    else:
        text_model = force_formats(ipynb_model)
        writes.append((text_path, write_text_script(text_model)))

    if exists_ipynb:
        writes.append((ipynb_path, write_ipynb_text(ipynb_model)))
    if exists_text:
        writes.append((text_path, write_text_script(text_model)))
    state["pairs"][pair_key(ipynb_rel)] = state_entry_for(ipynb_rel, text_rel, ipynb_model, text_model)
    writes.append((config.state_path(), json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"))
    pair = public_pair(status_for_pair(ipynb_rel, text_rel, config, state, "status"))
    pair["planned_writes"] = [config.rel(path) for path, _ in writes]
    return {"ok": True, "command": "pair", "root": ".", "pairs": [pair], "summary": summarize([pair])}, writes


def status_or_check(args, command):
    config = Config(args.config)
    if getattr(args, "all", False) and not args.config:
        raise MiniJupyError("--all requires --config")
    state = load_state(config)
    pairs = []
    if getattr(args, "all", False):
        for ipynb_rel, text_rel in discover_pairs(config, state):
            pairs.append(public_pair(status_for_pair(ipynb_rel, text_rel, config, state, command)))
    else:
        ipynb_rel, text_rel = pair_paths(args.input, config)
        pairs.append(public_pair(status_for_pair(ipynb_rel, text_rel, config, state, command)))
    result = {"ok": True, "command": command, "root": ".", "pairs": pairs, "summary": summarize(pairs)}
    if any(p["errors"] for p in pairs):
        result["ok"] = False
    return result, []


def sync_writes_for_pair(pair, config, state):
    ipynb_rel = pair["ipynb"]
    text_rel = pair["text"]
    ipynb_path = config.full(ipynb_rel)
    text_path = config.full(text_rel)
    source = pair["source"]
    models = pair["_models"]
    if source == "none":
        return []
    if pair["conflict"]:
        raise MiniJupyError("conflict without explicit source")
    if source == "ipynb":
        original = models["ipynb"] or read_ipynb(ipynb_path)
        model = force_formats(original)
        text_model = copy.deepcopy(model)
        writes = [(text_path, write_text_script(text_model))]
        if not has_pair_formats(original):
            writes.append((ipynb_path, write_ipynb_text(model)))
        ipynb_model = model
    elif source == "text":
        original = models["text"] or read_text(text_path)
        text_model = force_formats(original)
        ipynb_model = copy.deepcopy(text_model)
        if ipynb_path.exists() and models["ipynb"]:
            ipynb_model = preserve_outputs(ipynb_model, models["ipynb"])
        writes = [(ipynb_path, write_ipynb_text(ipynb_model))]
        if not has_pair_formats(original):
            writes.append((text_path, write_text_script(text_model)))
    else:
        raise MiniJupyError("no sync source selected")
    state["pairs"][pair_key(ipynb_rel)] = state_entry_for(ipynb_rel, text_rel, ipynb_model, text_model)
    return writes


def cmd_sync(args):
    config = Config(args.config)
    if getattr(args, "all", False) and not args.config:
        raise MiniJupyError("--all requires --config")
    state = load_state(config)
    selected = []
    if getattr(args, "all", False):
        for ipynb_rel, text_rel in discover_pairs(config, state):
            selected.append(status_for_pair(ipynb_rel, text_rel, config, state, "status", args.source))
    else:
        ipynb_rel, text_rel = pair_paths(args.input, config)
        selected.append(status_for_pair(ipynb_rel, text_rel, config, state, "status", args.source))

    for pair in selected:
        if pair["errors"]:
            raise MiniJupyError("; ".join(pair["errors"]))
        if pair["conflict"] and not args.source:
            raise MiniJupyError("conflict without explicit source")
        if pair["source"] == "none" and not load_state(config).get("pairs", {}).get(pair_key(pair["ipynb"])):
            if pair["exists"]["ipynb"] and pair["exists"]["text"] and not args.source:
                raise MiniJupyError("pair has no state; run pair or provide --source")

    writes = []
    for pair in selected:
        writes.extend(sync_writes_for_pair(pair, config, state))
    if writes:
        writes.append((config.state_path(), json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"))

    output_pairs = []
    for pair in selected:
        pub = public_pair(pair)
        pub["planned_writes"] = [config.rel(path) for path, _ in writes if config.rel(path) in {pair["ipynb"], pair["text"], STATE_NAME}]
        output_pairs.append(pub)
    return {"ok": True, "command": "sync", "root": ".", "pairs": output_pairs, "summary": summarize(output_pairs)}, writes


def build_parser():
    parser = argparse.ArgumentParser(prog="minijupy.py")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_input_config(p):
        p.add_argument("--input")
        p.add_argument("--config")

    p = sub.add_parser("inspect")
    add_input_config(p)

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
    p.add_argument("--source", choices=["ipynb", "text"])
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            if not args.input:
                raise MiniJupyError("--input is required")
            result, writes = cmd_inspect(args)
        elif args.command == "to-text":
            result, writes = cmd_to_text(args)
        elif args.command == "to-ipynb":
            result, writes = cmd_to_ipynb(args)
        elif args.command == "pair":
            result, writes = cmd_pair(args)
        elif args.command == "status":
            result, writes = status_or_check(args, "status")
        elif args.command == "check":
            result, writes = status_or_check(args, "check")
        elif args.command == "sync":
            result, writes = cmd_sync(args)
        else:
            raise MiniJupyError("unsupported command")
        apply_writes(writes)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except MiniJupyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

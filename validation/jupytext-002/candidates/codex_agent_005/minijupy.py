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
STATE_FILE = ".minijupy-state.json"
SUPPORTED_CELL_TYPES = {"code", "markdown", "raw"}


class MiniJupyError(Exception):
    pass


def fail(message):
    print(str(message), file=sys.stderr)
    return 1


def json_out(payload):
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def to_posix(path):
    return Path(path).as_posix()


def rel_to_root(path, root):
    try:
        rel = Path(path).resolve().relative_to(Path(root).resolve())
        return to_posix(rel)
    except ValueError:
        return to_posix(os.path.relpath(Path(path).resolve(), Path(root).resolve()))


def ensure_parent(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path, text):
    path = Path(path)
    ensure_parent(path)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path, data):
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise MiniJupyError(f"file not found: {path}")


def parse_config(config_path):
    if config_path is None:
        return {
            "root": Path.cwd().resolve(),
            "formats": FORMATS,
            "notebook_dir": None,
            "script_dir": None,
            "path": None,
        }

    path = Path(config_path).resolve()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise MiniJupyError(f"config not found: {config_path}")

    data = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise MiniJupyError("invalid config")
        key, value = [part.strip() for part in line.split("=", 1)]
        if key not in {"formats", "notebook_dir", "script_dir"}:
            raise MiniJupyError("invalid config")
        if len(value) < 2 or value[0] != '"' or value[-1] != '"':
            raise MiniJupyError("invalid config")
        data[key] = value[1:-1]

    formats = data.get("formats", FORMATS)
    if formats not in {FORMATS, "py:percent,ipynb"}:
        raise MiniJupyError("invalid config")
    has_nb = "notebook_dir" in data
    has_py = "script_dir" in data
    if has_nb != has_py:
        raise MiniJupyError("invalid config")
    return {
        "root": path.parent,
        "formats": formats,
        "notebook_dir": data.get("notebook_dir"),
        "script_dir": data.get("script_dir"),
        "path": path,
    }


def state_path(config):
    return Path(config["root"]) / STATE_FILE


def load_state(config):
    path = state_path(config)
    if not path.exists():
        return {"pairs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise MiniJupyError("malformed state file")
    if not isinstance(data, dict):
        return {"pairs": {}}
    pairs = data.get("pairs")
    if not isinstance(pairs, dict):
        data["pairs"] = {}
    return data


def write_state(config, state):
    atomic_write_json(state_path(config), state)


def parse_version(value):
    if value is None:
        return 1
    if not isinstance(value, int) or value < 0:
        raise MiniJupyError("invalid version")
    return value


def source_to_string(source):
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
    clean = {}
    tags = metadata.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise MiniJupyError("invalid cell metadata")
        clean["tags"] = list(tags)
    name = metadata.get("name")
    if name is not None:
        if not isinstance(name, str):
            raise MiniJupyError("invalid cell metadata")
        clean["name"] = name
    return clean


def make_metadata(metadata, version=None, formats=None):
    if not isinstance(metadata, dict):
        metadata = {}
    minijupy = metadata.get("minijupy")
    if not isinstance(minijupy, dict):
        minijupy = {}
    if version is None:
        version = parse_version(minijupy.get("version"))
    else:
        version = parse_version(version)
    out_minijupy = {"version": version}
    selected_formats = formats if formats is not None else minijupy.get("formats")
    if selected_formats is not None:
        if selected_formats not in {FORMATS, "py:percent,ipynb"}:
            raise MiniJupyError("invalid formats")
        out_minijupy["formats"] = selected_formats

    kernelspec = metadata.get("kernelspec")
    if not isinstance(kernelspec, dict):
        kernelspec = {}
    language_info = metadata.get("language_info")
    if not isinstance(language_info, dict):
        language_info = {}
    return {
        "kernelspec": copy.deepcopy(kernelspec),
        "language_info": copy.deepcopy(language_info),
        "minijupy": out_minijupy,
    }


def assign_and_validate_ids(cells):
    seen = set()
    for index, cell in enumerate(cells, start=1):
        cid = cell.get("id")
        if cid is None:
            cid = f"c{index}"
            cell["id"] = cid
        if not isinstance(cid, str) or not cid:
            raise MiniJupyError("invalid cell id")
        if cid in seen:
            raise MiniJupyError("duplicate cell ids")
        seen.add(cid)


def normalize_notebook_data(data, force_formats=None):
    if not isinstance(data, dict):
        raise MiniJupyError("malformed JSON notebook")
    if data.get("nbformat") != 4:
        raise MiniJupyError("unsupported notebook nbformat")
    nbformat_minor = data.get("nbformat_minor", 5)
    if not isinstance(nbformat_minor, int):
        nbformat_minor = 5
    metadata = make_metadata(data.get("metadata", {}), formats=force_formats)
    cells_in = data.get("cells", [])
    if not isinstance(cells_in, list):
        raise MiniJupyError("invalid cells")
    cells = []
    for raw in cells_in:
        if not isinstance(raw, dict):
            raise MiniJupyError("invalid cell")
        cell_type = raw.get("cell_type")
        if cell_type not in SUPPORTED_CELL_TYPES:
            raise MiniJupyError("unsupported cell type")
        cell = {
            "id": raw.get("id"),
            "cell_type": cell_type,
            "source": source_to_string(raw.get("source", "")),
            "metadata": clean_cell_metadata(raw.get("metadata", {})),
        }
        if cell_type == "code":
            cell["execution_count"] = raw.get("execution_count")
            cell["outputs"] = copy.deepcopy(raw.get("outputs", []))
            if not isinstance(cell["outputs"], list):
                raise MiniJupyError("invalid outputs")
        cells.append(cell)
    assign_and_validate_ids(cells)
    return {
        "nbformat": 4,
        "nbformat_minor": nbformat_minor,
        "metadata": metadata,
        "cells": cells,
    }


def read_ipynb(path, force_formats=None):
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError:
        raise MiniJupyError("malformed JSON notebook")
    return normalize_notebook_data(data, force_formats=force_formats)


HEADER_START_RE = re.compile(r"^# ---\s*$")
MARKER_RE = re.compile(r"^# %%\s*(.*)$")


def parse_header(lines):
    metadata = {"minijupy": {}}
    if not lines or not HEADER_START_RE.match(lines[0].rstrip("\n")):
        return metadata, 0

    block = []
    end = None
    for index in range(1, len(lines)):
        if HEADER_START_RE.match(lines[index].rstrip("\n")):
            end = index
            break
        line = lines[index]
        if line.startswith("#"):
            line = line[1:]
            if line.startswith(" "):
                line = line[1:]
        block.append(line.rstrip("\n"))
    if end is None:
        return metadata, 0

    section = None
    for raw in block:
        if not raw.strip():
            continue
        if not raw.startswith(" ") and raw.endswith(":"):
            section = raw[:-1].strip()
            continue
        if ":" not in raw:
            continue
        stripped = raw.strip()
        key, value = [part.strip() for part in stripped.split(":", 1)]
        value = value.strip().strip('"').strip("'")
        if section == "minijupy" and key == "formats":
            if value in {FORMATS, "py:percent,ipynb"}:
                metadata.setdefault("minijupy", {})["formats"] = value
        elif section == "minijupy" and key == "version":
            try:
                metadata.setdefault("minijupy", {})["version"] = int(value)
            except ValueError:
                raise MiniJupyError("invalid version")
        elif section == "kernelspec" and key == "name":
            metadata.setdefault("kernelspec", {})["name"] = value
    return metadata, end + 1


def parse_marker(line):
    match = MARKER_RE.match(line.rstrip("\n"))
    if not match:
        return None
    rest = match.group(1).strip()
    cell_type = "code"
    if rest.startswith("["):
        close = rest.find("]")
        if close == -1:
            raise MiniJupyError("malformed cell marker")
        label = rest[1:close].strip()
        if label in {"markdown", "md"}:
            cell_type = "markdown"
        elif label == "raw":
            cell_type = "raw"
        else:
            raise MiniJupyError("unsupported cell type")
        rest = rest[close + 1 :].strip()
    marker_meta = {}
    if rest:
        try:
            marker_meta = json.loads(rest)
        except json.JSONDecodeError:
            raise MiniJupyError("malformed percent marker JSON")
        if not isinstance(marker_meta, dict):
            raise MiniJupyError("malformed percent marker JSON")
        if set(marker_meta) - {"id", "tags", "name"}:
            raise MiniJupyError("malformed percent marker JSON")
    return cell_type, marker_meta


def markdown_from_body(lines):
    out = []
    for line in lines:
        if line.startswith("# "):
            out.append(line[2:])
        else:
            out.append(line)
    return "".join(out)


def body_from_lines(cell_type, lines):
    if cell_type == "markdown":
        return markdown_from_body(lines)
    return "".join(lines)


def cell_from_text(cell_type, marker_meta, body_lines):
    metadata = {}
    if "tags" in marker_meta:
        tags = marker_meta["tags"]
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise MiniJupyError("invalid cell metadata")
        metadata["tags"] = list(tags)
    if "name" in marker_meta:
        if not isinstance(marker_meta["name"], str):
            raise MiniJupyError("invalid cell metadata")
        metadata["name"] = marker_meta["name"]
    cell = {
        "id": marker_meta.get("id"),
        "cell_type": cell_type,
        "source": body_from_lines(cell_type, body_lines),
        "metadata": metadata,
    }
    if cell["id"] is not None and not isinstance(cell["id"], str):
        raise MiniJupyError("invalid cell id")
    if cell_type == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
    return cell


def read_percent(path, force_formats=None):
    text = read_text(path)
    lines = text.splitlines(True)
    header_metadata, start = parse_header(lines)
    metadata = make_metadata(header_metadata, formats=force_formats)

    cells = []
    current_type = None
    current_meta = {}
    current_lines = []
    before_first = True
    implicit_started = False

    def finish_current():
        nonlocal current_type, current_meta, current_lines
        if current_type is not None:
            cells.append(cell_from_text(current_type, current_meta, current_lines))
        current_type = None
        current_meta = {}
        current_lines = []

    for line in lines[start:]:
        marker = parse_marker(line)
        if marker is not None:
            if before_first and implicit_started:
                finish_current()
            elif not before_first:
                finish_current()
            before_first = False
            current_type, current_meta = marker
            current_lines = []
            continue
        if before_first:
            if not implicit_started:
                if line.strip() == "":
                    continue
                implicit_started = True
                current_type = "code"
                current_meta = {}
                current_lines = [line]
            else:
                current_lines.append(line)
        else:
            current_lines.append(line)
    if implicit_started or not before_first:
        finish_current()

    assign_and_validate_ids(cells)
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": metadata,
        "cells": cells,
    }


def read_any(path, force_formats=None):
    suffix = Path(path).suffix
    if suffix == ".ipynb":
        return "ipynb", read_ipynb(path, force_formats=force_formats)
    if suffix == ".py":
        return "text", read_percent(path, force_formats=force_formats)
    raise MiniJupyError("unsupported file type")


def notebook_version(nb):
    return parse_version(nb["metadata"].get("minijupy", {}).get("version"))


def notebook_formats(nb):
    return nb["metadata"].get("minijupy", {}).get("formats")


def with_formats(nb):
    out = copy.deepcopy(nb)
    out["metadata"].setdefault("minijupy", {})["formats"] = FORMATS
    out["metadata"].setdefault("minijupy", {})["version"] = notebook_version(out)
    return out


def marker_json(cell):
    data = {}
    if cell.get("id"):
        data["id"] = cell["id"]
    metadata = cell.get("metadata", {})
    if "tags" in metadata:
        data["tags"] = metadata["tags"]
    if "name" in metadata:
        data["name"] = metadata["name"]
    if not data:
        return ""
    return " " + json.dumps(data, sort_keys=True, separators=(",", ":"))


def write_percent_string(nb):
    nb = with_formats(nb)
    minijupy = nb["metadata"]["minijupy"]
    lines = [
        "# ---\n",
        "# minijupy:\n",
        f"#   formats: {minijupy.get('formats', FORMATS)}\n",
        f"#   version: {notebook_version(nb)}\n",
    ]
    kernel_name = nb["metadata"].get("kernelspec", {}).get("name")
    if kernel_name:
        lines.extend(["# kernelspec:\n", f"#   name: {kernel_name}\n"])
    lines.append("# ---\n")
    for cell in nb["cells"]:
        cell_type = cell["cell_type"]
        if cell_type == "markdown":
            marker = "# %% [markdown]"
        elif cell_type == "raw":
            marker = "# %% [raw]"
        else:
            marker = "# %%"
        lines.append(marker + marker_json(cell) + "\n")
        source = cell.get("source", "")
        if cell_type == "markdown":
            for part in source.splitlines(True):
                lines.append("# " + part)
            if source == "":
                pass
        else:
            lines.append(source)
        if source and not source.endswith("\n"):
            lines.append("\n")
    return "".join(lines)


def notebook_for_json(nb):
    out = with_formats(nb)
    for cell in out["cells"]:
        if cell["cell_type"] == "code":
            cell.setdefault("execution_count", None)
            cell.setdefault("outputs", [])
        else:
            cell.pop("execution_count", None)
            cell.pop("outputs", None)
    return out


def write_ipynb_string(nb):
    return json.dumps(notebook_for_json(nb), indent=2, sort_keys=True) + "\n"


def comparable_model(nb, include_outputs=False):
    out = {
        "version": notebook_version(nb),
        "formats": notebook_formats(nb),
        "kernelspec_name": nb["metadata"].get("kernelspec", {}).get("name"),
        "cells": [],
    }
    for cell in nb["cells"]:
        item = {
            "id": cell.get("id"),
            "cell_type": cell["cell_type"],
            "source": cell.get("source", ""),
            "tags": cell.get("metadata", {}).get("tags", []),
            "name": cell.get("metadata", {}).get("name"),
        }
        if include_outputs and cell["cell_type"] == "code":
            item["execution_count"] = cell.get("execution_count")
            item["outputs"] = cell.get("outputs", [])
        out["cells"].append(item)
    return out


def stable_hash(nb):
    payload = json.dumps(comparable_model(nb, include_outputs=True), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_hash(cell):
    payload = json.dumps(
        {"cell_type": cell["cell_type"], "source": cell.get("source", "")},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def preserve_outputs(new_nb, old_nb):
    old_cells = old_nb.get("cells", [])
    used = set()
    by_id = {}
    for idx, cell in enumerate(old_cells):
        cid = cell.get("id")
        if cid and cell.get("cell_type") == "code":
            by_id[cid] = idx

    for index, cell in enumerate(new_nb["cells"]):
        if cell["cell_type"] != "code":
            cell.pop("execution_count", None)
            cell.pop("outputs", None)
            continue
        chosen = None
        cid = cell.get("id")
        if cid in by_id and by_id[cid] not in used:
            chosen = by_id[cid]
        if chosen is None:
            new_hash = source_hash(cell)
            for old_index, old_cell in enumerate(old_cells):
                if old_index in used or old_cell.get("cell_type") != "code":
                    continue
                if source_hash(old_cell) == new_hash:
                    chosen = old_index
                    break
        if chosen is None and index < len(old_cells):
            old_cell = old_cells[index]
            if index not in used and old_cell.get("cell_type") == "code":
                chosen = index
        if chosen is not None:
            used.add(chosen)
            old_cell = old_cells[chosen]
            cell["execution_count"] = old_cell.get("execution_count")
            cell["outputs"] = copy.deepcopy(old_cell.get("outputs", []))
        else:
            cell["execution_count"] = None
            cell["outputs"] = []
    return new_nb


def absolute_input(path):
    return Path(path).resolve()


def is_under(path, directory):
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
        return True
    except ValueError:
        return False


def pair_paths(input_path, config):
    path = absolute_input(input_path)
    suffix = path.suffix
    if suffix not in {".ipynb", ".py"}:
        raise MiniJupyError("unsupported file type")
    root = Path(config["root"]).resolve()
    nb_dir = config.get("notebook_dir")
    py_dir = config.get("script_dir")
    if nb_dir and py_dir:
        nb_root = (root / nb_dir).resolve()
        py_root = (root / py_dir).resolve()
        if suffix == ".ipynb":
            if not is_under(path, nb_root):
                raise MiniJupyError("path mismatch")
            rel = path.resolve().relative_to(nb_root).with_suffix(".py")
            ipynb = path
            text = py_root / rel
        else:
            if not is_under(path, py_root):
                raise MiniJupyError("path mismatch")
            rel = path.resolve().relative_to(py_root).with_suffix(".ipynb")
            ipynb = nb_root / rel
            text = path
    else:
        if suffix == ".ipynb":
            ipynb = path
            text = path.with_suffix(".py")
        else:
            ipynb = path.with_suffix(".ipynb")
            text = path
    return ipynb.resolve(), text.resolve()


def state_key(ipynb, config):
    return rel_to_root(ipynb, config["root"])


def rel_pair(ipynb, text, config):
    return rel_to_root(ipynb, config["root"]), rel_to_root(text, config["root"])


def existing_pair_notebooks(ipynb, text):
    nb = txt = None
    if Path(ipynb).exists():
        nb = read_ipynb(ipynb)
    if Path(text).exists():
        txt = read_percent(text)
    return nb, txt


def state_entry_for(state, key):
    entry = state.get("pairs", {}).get(key)
    if isinstance(entry, dict):
        return entry
    return None


def last_versions(entry):
    last = entry.get("last_synced", {}) if entry else {}
    ip_last = last.get("ipynb_version")
    tx_last = last.get("text_version")
    return ip_last if isinstance(ip_last, int) else None, tx_last if isinstance(tx_last, int) else None


def determine_source(ip_ver, tx_ver, entry, exists, explicit=None):
    if explicit in {"ipynb", "text"}:
        return explicit, False, []
    if not exists["ipynb"] and not exists["text"]:
        return "none", False, ["both sides missing"]
    if exists["ipynb"] and not exists["text"]:
        return "ipynb", False, []
    if exists["text"] and not exists["ipynb"]:
        return "text", False, []
    if entry is None:
        return "none", False, ["unpaired"]
    last_ip, last_tx = last_versions(entry)
    ip_changed = last_ip is not None and ip_ver is not None and ip_ver > last_ip
    tx_changed = last_tx is not None and tx_ver is not None and tx_ver > last_tx
    conflict = bool(ip_changed and tx_changed)
    if conflict:
        return "none", True, []
    if ip_changed:
        return "ipynb", False, []
    if tx_changed:
        return "text", False, []
    return "none", False, []


def compare_models(ip_nb, tx_nb):
    diffs = []
    if notebook_version(ip_nb) != notebook_version(tx_nb):
        diffs.append("version")
    if notebook_formats(ip_nb) != notebook_formats(tx_nb):
        diffs.append("formats")
    ip_cells = ip_nb["cells"]
    tx_cells = tx_nb["cells"]
    if len(ip_cells) != len(tx_cells):
        diffs.append("cell_count")
    for left, right in zip(ip_cells, tx_cells):
        if left["cell_type"] != right["cell_type"] and "cell_type" not in diffs:
            diffs.append("cell_type")
        if left.get("source", "") != right.get("source", "") and "source" not in diffs:
            diffs.append("source")
        if left.get("id") != right.get("id") and "id" not in diffs:
            diffs.append("id")
        if left.get("metadata", {}).get("tags", []) != right.get("metadata", {}).get("tags", []) and "tags" not in diffs:
            diffs.append("tags")
        if left.get("metadata", {}).get("name") != right.get("metadata", {}).get("name") and "name" not in diffs:
            diffs.append("name")
    return diffs


def pair_status(ipynb, text, config, state, command="status", explicit_source=None):
    ip_rel, tx_rel = rel_pair(ipynb, text, config)
    key = state_key(ipynb, config)
    entry = state_entry_for(state, key)
    exists = {"ipynb": Path(ipynb).exists(), "text": Path(text).exists()}
    errors = []
    missing = []
    versions = {"ipynb": None, "text": None, "last_ipynb": None, "last_text": None}
    roundtrip_ok = True
    differences = []
    ip_nb = tx_nb = None

    try:
        if exists["ipynb"]:
            ip_nb = read_ipynb(ipynb)
            versions["ipynb"] = notebook_version(ip_nb)
        else:
            missing.append(ip_rel)
        if exists["text"]:
            tx_nb = read_percent(text)
            versions["text"] = notebook_version(tx_nb)
        else:
            missing.append(tx_rel)
    except MiniJupyError as exc:
        errors.append(str(exc))
        roundtrip_ok = False

    if entry:
        last_ip, last_tx = last_versions(entry)
        versions["last_ipynb"] = last_ip
        versions["last_text"] = last_tx
        if (
            command == "check"
            and ((last_ip is not None and versions["ipynb"] is not None and last_ip > versions["ipynb"])
                 or (last_tx is not None and versions["text"] is not None and last_tx > versions["text"]))
        ):
            differences.append("state")
            roundtrip_ok = False

    source, conflict, source_errors = determine_source(
        versions["ipynb"], versions["text"], entry, exists, explicit=explicit_source
    )
    errors.extend(source_errors if command == "sync" else [])

    if command == "check":
        if missing:
            roundtrip_ok = False
        if ip_nb is not None and tx_nb is not None:
            differences.extend(diff for diff in compare_models(ip_nb, tx_nb) if diff not in differences)
            if differences:
                roundtrip_ok = False
    elif ip_nb is not None and tx_nb is not None:
        differences = compare_models(ip_nb, tx_nb)
        roundtrip_ok = not differences
    else:
        roundtrip_ok = False if command == "check" else True

    planned = []
    if not errors and not conflict:
        if source == "ipynb":
            if ip_nb is not None and notebook_formats(ip_nb) != FORMATS:
                planned.append(ip_rel)
            planned.append(tx_rel)
            planned.append(STATE_FILE)
        elif source == "text":
            if tx_nb is not None and notebook_formats(tx_nb) != FORMATS:
                planned.append(tx_rel)
            planned.append(ip_rel)
            planned.append(STATE_FILE)

    return {
        "ipynb": ip_rel,
        "text": tx_rel,
        "exists": exists,
        "versions": versions,
        "source": "none" if conflict else source,
        "conflict": conflict,
        "missing": missing,
        "planned_writes": planned,
        "roundtrip_ok": roundtrip_ok,
        "differences": differences,
        "errors": errors,
    }


def discover_pairs(config):
    if config.get("path") is None:
        raise MiniJupyError("--all requires --config")
    root = Path(config["root"]).resolve()
    candidates = []
    nb_dir = config.get("notebook_dir")
    py_dir = config.get("script_dir")
    if nb_dir and py_dir:
        roots = [(root / nb_dir, "*.ipynb"), (root / py_dir, "*.py")]
    else:
        roots = [(root, "*.ipynb"), (root, "*.py")]
    for base, pattern in roots:
        if base.exists():
            candidates.extend(sorted(base.rglob(pattern)))
    pairs = {}
    for candidate in candidates:
        ipynb, text = pair_paths(candidate, config)
        key = state_key(ipynb, config)
        existing = pairs.get(key)
        pair_value = (ipynb, text)
        if existing and existing != pair_value:
            raise MiniJupyError("duplicate paired paths")
        pairs[key] = pair_value
    return [pairs[key] for key in sorted(pairs)]


def update_state_entry(config, state, ipynb, text, ip_nb, tx_nb):
    key = state_key(ipynb, config)
    ip_rel, tx_rel = rel_pair(ipynb, text, config)
    state.setdefault("pairs", {})[key] = {
        "ipynb": ip_rel,
        "text": tx_rel,
        "last_synced": {
            "ipynb_version": notebook_version(ip_nb),
            "text_version": notebook_version(tx_nb),
            "ipynb_hash": stable_hash(ip_nb),
            "text_hash": stable_hash(tx_nb),
        },
    }


def command_inspect(args, config):
    fmt, nb = read_any(args.input)
    json_out(
        {
            "ok": True,
            "command": "inspect",
            "path": rel_to_root(args.input, config["root"]),
            "format": fmt,
            "version": notebook_version(nb),
            "notebook": nb,
        }
    )


def command_to_text(args, config):
    if Path(args.input).suffix != ".ipynb" or Path(args.output).suffix != ".py":
        raise MiniJupyError("unsupported file type")
    nb = read_ipynb(args.input)
    atomic_write_text(args.output, write_percent_string(nb))
    json_out(
        {
            "ok": True,
            "command": "to-text",
            "input": rel_to_root(args.input, config["root"]),
            "output": rel_to_root(args.output, config["root"]),
        }
    )


def command_to_ipynb(args, config):
    if Path(args.input).suffix != ".py" or Path(args.output).suffix != ".ipynb":
        raise MiniJupyError("unsupported file type")
    nb = read_percent(args.input)
    atomic_write_text(args.output, write_ipynb_string(nb))
    json_out(
        {
            "ok": True,
            "command": "to-ipynb",
            "input": rel_to_root(args.input, config["root"]),
            "output": rel_to_root(args.output, config["root"]),
        }
    )


def command_pair(args, config):
    ipynb, text = pair_paths(args.input, config)
    if not ipynb.exists() and not text.exists():
        raise MiniJupyError("both sides missing")
    state = load_state(config)

    ip_nb = read_ipynb(ipynb, force_formats=FORMATS) if ipynb.exists() else None
    tx_nb = read_percent(text, force_formats=FORMATS) if text.exists() else None
    writes = []
    if ip_nb is None:
        ip_nb = tx_nb
        writes.append((ipynb, write_ipynb_string(ip_nb)))
        writes.append((text, write_percent_string(tx_nb)))
    elif tx_nb is None:
        tx_nb = ip_nb
        writes.append((ipynb, write_ipynb_string(ip_nb)))
        writes.append((text, write_percent_string(tx_nb)))
    else:
        writes.append((ipynb, write_ipynb_string(ip_nb)))
        writes.append((text, write_percent_string(tx_nb)))

    for path, content in writes:
        atomic_write_text(path, content)
    ip_nb = read_ipynb(ipynb, force_formats=FORMATS)
    tx_nb = read_percent(text, force_formats=FORMATS)
    update_state_entry(config, state, ipynb, text, ip_nb, tx_nb)
    write_state(config, state)
    pair = pair_status(ipynb, text, config, state, command="status")
    json_out({"ok": True, "command": "pair", "root": rel_to_root(config["root"], config["root"]), "pairs": [pair]})


def command_status_like(args, config, command):
    state = load_state(config)
    if args.all:
        pairs = discover_pairs(config)
    else:
        pairs = [pair_paths(args.input, config)]
    pair_objects = [pair_status(ip, tx, config, state, command=command) for ip, tx in pairs]
    summary = {
        "pairs": len(pair_objects),
        "conflicts": sum(1 for pair in pair_objects if pair["conflict"]),
        "missing": sum(len(pair["missing"]) for pair in pair_objects),
        "planned_writes": sum(len(pair["planned_writes"]) for pair in pair_objects),
        "errors": sum(len(pair["errors"]) for pair in pair_objects),
    }
    json_out(
        {
            "ok": summary["errors"] == 0,
            "command": command,
            "root": rel_to_root(config["root"], config["root"]),
            "pairs": pair_objects,
            "summary": summary,
        }
    )
    if summary["errors"] and command == "check":
        raise MiniJupyError("check failed")


def plan_sync_pair(ipynb, text, config, state, explicit_source=None):
    status = pair_status(ipynb, text, config, state, command="sync", explicit_source=explicit_source)
    if status["errors"]:
        raise MiniJupyError("; ".join(status["errors"]))
    if status["conflict"]:
        raise MiniJupyError("conflict without explicit source")
    source = status["source"]
    writes = []
    new_state = None

    if source == "none":
        return status, writes, None
    if source == "ipynb":
        if not Path(ipynb).exists():
            raise MiniJupyError("missing ipynb source")
        original_ip_nb = read_ipynb(ipynb)
        ip_nb = with_formats(original_ip_nb)
        if notebook_formats(original_ip_nb) != FORMATS:
            writes.append((ipynb, write_ipynb_string(ip_nb)))
        tx_nb = with_formats(ip_nb)
        writes.append((text, write_percent_string(tx_nb)))
        new_state = (with_formats(ip_nb), read_percent_from_string(write_percent_string(tx_nb)))
    elif source == "text":
        if not Path(text).exists():
            raise MiniJupyError("missing text source")
        original_tx_nb = read_percent(text)
        tx_nb = with_formats(original_tx_nb)
        if notebook_formats(original_tx_nb) != FORMATS:
            writes.append((text, write_percent_string(tx_nb)))
        ip_nb = with_formats(tx_nb)
        if Path(ipynb).exists():
            old_ip = read_ipynb(ipynb)
            ip_nb = preserve_outputs(ip_nb, old_ip)
        writes.append((ipynb, write_ipynb_string(ip_nb)))
        new_state = (ip_nb, with_formats(tx_nb))
    return status, writes, new_state


def read_percent_from_string(text):
    fd, tmp = tempfile.mkstemp(prefix=".minijupy-parse-", suffix=".py")
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        tmp_path.write_text(text, encoding="utf-8")
        return read_percent(tmp_path, force_formats=FORMATS)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def command_sync(args, config):
    state = load_state(config)
    pairs = discover_pairs(config) if args.all else [pair_paths(args.input, config)]
    planned = []
    state_updates = []
    statuses = []
    for ipynb, text in pairs:
        status, writes, new_state = plan_sync_pair(ipynb, text, config, state, explicit_source=args.source)
        statuses.append(status)
        planned.extend(writes)
        if new_state is not None:
            state_updates.append((ipynb, text, new_state[0], new_state[1]))

    for path, content in planned:
        atomic_write_text(path, content)
    for ipynb, text, ip_nb, tx_nb in state_updates:
        update_state_entry(config, state, ipynb, text, ip_nb, tx_nb)
    if state_updates:
        write_state(config, state)
    final_state = load_state(config)
    final_pairs = [
        pair_status(ip, tx, config, final_state, command="sync", explicit_source=args.source)
        for ip, tx in pairs
    ]
    json_out(
        {
            "ok": True,
            "command": "sync",
            "root": rel_to_root(config["root"], config["root"]),
            "pairs": final_pairs,
            "summary": {
                "pairs": len(final_pairs),
                "conflicts": sum(1 for pair in final_pairs if pair["conflict"]),
                "missing": sum(len(pair["missing"]) for pair in final_pairs),
                "planned_writes": sum(len(pair["planned_writes"]) for pair in statuses),
                "errors": sum(len(pair["errors"]) for pair in final_pairs),
            },
        }
    )


def build_parser():
    parser = argparse.ArgumentParser(prog="minijupy.py")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_p = sub.add_parser("inspect")
    inspect_p.add_argument("--input", required=True)
    inspect_p.add_argument("--config")

    to_text = sub.add_parser("to-text")
    to_text.add_argument("--input", required=True)
    to_text.add_argument("--output", required=True)
    to_text.add_argument("--config")

    to_ipynb = sub.add_parser("to-ipynb")
    to_ipynb.add_argument("--input", required=True)
    to_ipynb.add_argument("--output", required=True)
    to_ipynb.add_argument("--config")

    pair = sub.add_parser("pair")
    pair.add_argument("--input", required=True)
    pair.add_argument("--config")

    for name in ("status", "check", "sync"):
        cmd = sub.add_parser(name)
        group = cmd.add_mutually_exclusive_group(required=True)
        group.add_argument("--input")
        group.add_argument("--all", action="store_true")
        cmd.add_argument("--config")
        if name == "sync":
            cmd.add_argument("--source", choices=["ipynb", "text"])
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        config = parse_config(getattr(args, "config", None))
        if getattr(args, "all", False) and config.get("path") is None:
            raise MiniJupyError("--all requires --config")
        if args.command == "inspect":
            command_inspect(args, config)
        elif args.command == "to-text":
            command_to_text(args, config)
        elif args.command == "to-ipynb":
            command_to_ipynb(args, config)
        elif args.command == "pair":
            command_pair(args, config)
        elif args.command == "status":
            command_status_like(args, config, "status")
        elif args.command == "check":
            command_status_like(args, config, "check")
        elif args.command == "sync":
            command_sync(args, config)
        else:
            raise MiniJupyError("unsupported command")
        return 0
    except MiniJupyError as exc:
        return fail(exc)


if __name__ == "__main__":
    raise SystemExit(main())

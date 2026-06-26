#!/usr/bin/env python3
import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path


SUPPORTED_FORMATS = "ipynb,py:percent"


class MiniJupyError(Exception):
    pass


def compact(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def emit(obj):
    print(compact(obj))


def fail(msg):
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def path_s(p):
    return Path(p).as_posix()


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception as exc:
        raise MiniJupyError(f"malformed ipynb JSON: {exc}")


def write_text_atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def write_json_atomic(path, obj):
    write_text_atomic(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def config_for(input_path, config_arg):
    input_path = Path(input_path)
    if config_arg:
        cfg = Path(config_arg)
    else:
        cfg = input_path.parent / "minijupy.toml"

    config = {"formats": SUPPORTED_FORMATS, "notebook_dir": "", "script_dir": ""}
    base = cfg.parent if cfg.exists() else Path.cwd()
    if not cfg.exists():
        return config, base

    for raw in cfg.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise MiniJupyError("invalid config line")
        key, value = [x.strip() for x in line.split("=", 1)]
        if key not in config:
            continue
        if len(value) < 2 or value[0] != '"' or value[-1] != '"':
            raise MiniJupyError("invalid config value")
        config[key] = value[1:-1]
    if config["formats"] != SUPPORTED_FORMATS:
        raise MiniJupyError("unsupported formats")
    return config, base


def is_under(path, root):
    path = Path(path)
    root = Path(root)
    try:
        rel = path.relative_to(root)
        return True, rel
    except ValueError:
        return False, None


def paired_paths(input_file, config_arg=None):
    cfg, base = config_for(input_file, config_arg)
    p = Path(input_file)
    if p.suffix not in {".ipynb", ".py"}:
        raise MiniJupyError("unsupported input extension")

    if cfg["notebook_dir"] and cfg["script_dir"]:
        nb_root = base / cfg["notebook_dir"]
        py_root = base / cfg["script_dir"]
        if p.suffix == ".ipynb":
            ok, rel = is_under(p, nb_root)
            if not ok:
                raise MiniJupyError("input outside notebook_dir")
            ipynb = p
            py = (py_root / rel).with_suffix(".py")
        else:
            ok, rel = is_under(p, py_root)
            if not ok:
                raise MiniJupyError("input outside script_dir")
            py = p
            ipynb = (nb_root / rel).with_suffix(".ipynb")
    else:
        if p.suffix == ".ipynb":
            ipynb = p
            py = p.with_suffix(".py")
        else:
            py = p
            ipynb = p.with_suffix(".ipynb")
    return path_s(ipynb), path_s(py), cfg


def normalize_notebook(obj, warnings=None):
    warnings = warnings if warnings is not None else []
    if not isinstance(obj, dict):
        raise MiniJupyError("notebook must be an object")

    src_meta = obj.get("metadata") or {}
    if not isinstance(src_meta, dict):
        raise MiniJupyError("metadata must be an object")
    metadata = {}
    for key in ("minijupy", "kernelspec"):
        if key in src_meta:
            metadata[key] = deepcopy(src_meta[key])
    for key in src_meta:
        if key not in {"minijupy", "kernelspec"}:
            warnings.append(f"unsupported-metadata:{key}")

    cells = obj.get("cells")
    if not isinstance(cells, list):
        raise MiniJupyError("cells must be an array")

    seen = set()
    norm_cells = []
    for idx, cell in enumerate(cells, start=1):
        if not isinstance(cell, dict):
            raise MiniJupyError("cell must be an object")
        ctype = cell.get("cell_type", "code")
        if ctype not in {"code", "markdown", "raw"}:
            raise MiniJupyError("unsupported cell type")
        cid = cell.get("id") or f"c{idx}"
        if cid in seen:
            raise MiniJupyError("duplicate cell id")
        seen.add(cid)
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        if not isinstance(source, str):
            raise MiniJupyError("cell source must be string")
        src_cell_meta = cell.get("metadata") or {}
        if not isinstance(src_cell_meta, dict):
            raise MiniJupyError("cell metadata must be object")
        cell_meta = {}
        if isinstance(src_cell_meta.get("tags"), list):
            cell_meta["tags"] = list(src_cell_meta["tags"])
        if isinstance(src_cell_meta.get("name"), str):
            cell_meta["name"] = src_cell_meta["name"]
        for key in src_cell_meta:
            if key not in {"tags", "name"}:
                warnings.append(f"unsupported-cell-metadata:{key}")
        if ctype == "code":
            execution_count = cell.get("execution_count")
            outputs = cell.get("outputs") if isinstance(cell.get("outputs"), list) else []
        else:
            execution_count = None
            outputs = []
        norm_cells.append({
            "id": cid,
            "cell_type": ctype,
            "source": source,
            "metadata": cell_meta,
            "execution_count": execution_count,
            "outputs": outputs,
        })
    return {"metadata": metadata, "cells": norm_cells}, warnings


def version_of(model):
    mj = model.get("metadata", {}).get("minijupy", {})
    version = mj.get("version", 0) if isinstance(mj, dict) else 0
    return version if isinstance(version, int) and version >= 0 else 0


def formats_of(model, cfg=None):
    mj = model.get("metadata", {}).get("minijupy", {})
    if isinstance(mj, dict) and isinstance(mj.get("formats"), str):
        return mj["formats"]
    return (cfg or {}).get("formats", SUPPORTED_FORMATS)


def set_minijupy(model, formats, version):
    model.setdefault("metadata", {})
    model["metadata"]["minijupy"] = {"formats": formats, "version": version}


def marker_kind(line):
    if line.startswith("# %% [markdown]"):
        return "markdown", line[len("# %% [markdown]"):]
    if line.startswith("# %% [raw]"):
        return "raw", line[len("# %% [raw]"):]
    if line.startswith("# %%"):
        return "code", line[len("# %%"):]
    return None, None


def parse_percent(path):
    lines = Path(path).read_text().splitlines()
    pos = 0
    metadata = {}
    warnings = []

    if lines and lines[0] == "# ---":
        pos = 1
        while pos < len(lines) and lines[pos] != "# ---":
            line = lines[pos]
            if not line.startswith("# ") or ":" not in line[2:]:
                raise MiniJupyError("bad header block")
            key, value = line[2:].split(":", 1)
            key = key.strip()
            value = value.strip()
            if key in {"minijupy", "kernelspec"}:
                try:
                    metadata[key] = json.loads(value)
                except Exception as exc:
                    raise MiniJupyError(f"malformed header JSON: {exc}")
            else:
                warnings.append(f"unsupported-header:{key}")
            pos += 1
        if pos >= len(lines) or lines[pos] != "# ---":
            raise MiniJupyError("unterminated header")
        pos += 1

    cells = []
    seen = set()
    auto = 1

    def finish(ctype, marker, body):
        nonlocal auto
        if ctype is None:
            return
        if body and body[-1] == "":
            body = body[:-1]
        marker = marker.strip()
        marker_obj = {}
        if marker:
            if not marker.startswith("{"):
                raise MiniJupyError("malformed cell marker")
            try:
                raw = json.loads(marker)
            except Exception as exc:
                raise MiniJupyError(f"malformed marker JSON: {exc}")
            if not isinstance(raw, dict):
                raise MiniJupyError("marker metadata must be object")
            for key in ("id", "tags", "name"):
                if key in raw:
                    marker_obj[key] = raw[key]
            for key in raw:
                if key not in {"id", "tags", "name"}:
                    warnings.append(f"unsupported-marker:{key}")
        cid = marker_obj.get("id") or f"c{auto}"
        auto += 1
        if cid in seen:
            raise MiniJupyError("duplicate cell id")
        seen.add(cid)
        cell_meta = {}
        if isinstance(marker_obj.get("tags"), list):
            cell_meta["tags"] = marker_obj["tags"]
        if isinstance(marker_obj.get("name"), str):
            cell_meta["name"] = marker_obj["name"]
        if ctype in {"markdown", "raw"}:
            source_lines = []
            for b in body:
                if b == "#":
                    source_lines.append("")
                elif b.startswith("# "):
                    source_lines.append(b[2:])
                else:
                    source_lines.append(b)
            source = "\n".join(source_lines)
            execution_count = None
            outputs = []
        else:
            source = "\n".join(body)
            execution_count = None
            outputs = []
        cells.append({
            "id": cid,
            "cell_type": ctype,
            "source": source,
            "metadata": cell_meta,
            "execution_count": execution_count,
            "outputs": outputs,
        })

    current_type = None
    current_marker = ""
    current_body = []
    while pos < len(lines):
        ctype, marker = marker_kind(lines[pos])
        if ctype:
            finish(current_type, current_marker, current_body)
            current_type = ctype
            current_marker = marker
            current_body = []
        else:
            if current_type is None and lines[pos].strip():
                raise MiniJupyError("content before first marker")
            if current_type is not None:
                current_body.append(lines[pos])
        pos += 1
    finish(current_type, current_marker, current_body)
    return {"metadata": metadata, "cells": cells}, warnings


def read_model(path):
    p = Path(path)
    if not p.exists():
        raise MiniJupyError("input file does not exist")
    if p.suffix == ".ipynb":
        return normalize_notebook(read_json(p))
    if p.suffix == ".py":
        return parse_percent(p)
    raise MiniJupyError("unsupported input extension")


def write_percent(model):
    out = []
    meta = model.get("metadata", {})
    if "minijupy" in meta or "kernelspec" in meta:
        out.append("# ---")
        if "minijupy" in meta:
            out.append("# minijupy: " + compact(meta["minijupy"]))
        if "kernelspec" in meta:
            out.append("# kernelspec: " + compact(meta["kernelspec"]))
        out.append("# ---")
    for idx, cell in enumerate(model["cells"]):
        if out:
            out.append("")
        ctype = cell["cell_type"]
        marker = "# %%"
        if ctype == "markdown":
            marker += " [markdown]"
        elif ctype == "raw":
            marker += " [raw]"
        marker_meta = {"id": cell["id"]}
        if "tags" in cell.get("metadata", {}):
            marker_meta["tags"] = cell["metadata"]["tags"]
        if "name" in cell.get("metadata", {}):
            marker_meta["name"] = cell["metadata"]["name"]
        marker += " " + compact(marker_meta)
        out.append(marker)
        for line in cell.get("source", "").split("\n") if cell.get("source", "") != "" else []:
            if ctype == "code":
                out.append(line)
            else:
                out.append("#" if line == "" else "# " + line)
    return "\n".join(out) + "\n"


def inspect_model(input_file, config_arg=None):
    ipynb, py, cfg = paired_paths(input_file, config_arg)
    model, warnings = read_model(input_file)
    fmt = "ipynb" if Path(input_file).suffix == ".ipynb" else "text"
    cells = []
    for cell in model["cells"]:
        cells.append({
            "id": cell["id"],
            "cell_type": cell["cell_type"],
            "source": cell["source"],
            "metadata": cell["metadata"],
            "execution_count": cell["execution_count"],
            "has_outputs": bool(cell["outputs"]),
        })
    return {
        "input": path_s(input_file),
        "format": fmt,
        "paired_paths": [ipynb, py],
        "version": version_of(model),
        "formats": formats_of(model, cfg),
        "cells": cells,
        "warnings": warnings,
    }


def model_for_text_roundtrip(model):
    m = deepcopy(model)
    for cell in m["cells"]:
        cell["execution_count"] = None
        cell["outputs"] = []
    return m


def comparable(model):
    meta = {}
    for key in ("minijupy", "kernelspec"):
        if key in model.get("metadata", {}):
            meta[key] = model["metadata"][key]
    cells = []
    for cell in model["cells"]:
        cells.append({
            "cell_type": cell["cell_type"],
            "source": cell["source"],
            "metadata": cell["metadata"],
        })
    return {"metadata": meta, "cells": cells}


def status_report(input_file, config_arg=None):
    ipynb, py, cfg = paired_paths(input_file, config_arg)
    paths = {"ipynb": ipynb, "text": py}
    exists = {side: Path(path).exists() for side, path in paths.items()}
    missing = [path for side, path in paths.items() if not exists[side]]
    errors = []
    models = {}
    versions = {}

    for side, path in paths.items():
        if exists[side]:
            try:
                models[side], _ = read_model(path)
                versions[side] = version_of(models[side])
            except Exception as exc:
                errors.append(f"{side}:{exc}")

    source = "none"
    would_write = []
    roundtrip_ok = False
    differences = []

    if errors:
        pass
    elif exists["ipynb"] and not exists["text"]:
        source = "ipynb"
        would_write = [py]
    elif exists["text"] and not exists["ipynb"]:
        source = "text"
        would_write = [ipynb]
    elif exists["ipynb"] and exists["text"]:
        if versions["ipynb"] > versions["text"]:
            source = "ipynb"
            would_write = [py]
        elif versions["text"] > versions["ipynb"]:
            source = "text"
            would_write = [ipynb]
        else:
            source = "none"
        roundtrip_ok = comparable(models["ipynb"]) == comparable(models["text"])
        if not roundtrip_ok:
            differences.append("model")

    return {
        "paired_paths": [ipynb, py],
        "source": source,
        "would_write": would_write,
        "roundtrip_ok": roundtrip_ok,
        "differences": differences,
        "missing": missing,
        "errors": errors,
    }


def to_text(input_file, output_file):
    if Path(input_file).suffix != ".ipynb":
        raise MiniJupyError("to-text input must be .ipynb")
    model, _ = read_model(input_file)
    write_text_atomic(output_file, write_percent(model))
    emit({"written": path_s(output_file), "cells": len(model["cells"])})


def to_ipynb(input_file, output_file):
    if Path(input_file).suffix != ".py":
        raise MiniJupyError("to-ipynb input must be .py")
    model, _ = read_model(input_file)
    write_json_atomic(output_file, model)
    emit({"written": path_s(output_file), "cells": len(model["cells"])})


def pair(input_file, formats, config_arg=None):
    if Path(input_file).suffix != ".ipynb":
        raise MiniJupyError("pair input must be .ipynb")
    if formats != SUPPORTED_FORMATS:
        raise MiniJupyError("unsupported formats")
    ipynb, py, _ = paired_paths(input_file, config_arg)
    model, _ = read_model(input_file)
    version = version_of(model)
    set_minijupy(model, formats, version)
    write_json_atomic(ipynb, model)
    write_text_atomic(py, write_percent(model))
    emit({"paired_paths": [ipynb, py], "version": version})


def preserve_outputs(source_model, old_ipynb_model=None):
    old_cells = old_ipynb_model["cells"] if old_ipynb_model else []
    by_id = {c["id"]: c for c in old_cells if c.get("id")}
    out = deepcopy(source_model)
    for idx, cell in enumerate(out["cells"]):
        old = by_id.get(cell.get("id"))
        if old is None and idx < len(old_cells):
            old = old_cells[idx]
        if cell["cell_type"] == "code" and old is not None:
            cell["execution_count"] = old.get("execution_count")
            cell["outputs"] = deepcopy(old.get("outputs", []))
        elif cell["cell_type"] == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        else:
            cell["execution_count"] = None
            cell["outputs"] = []
    return out


def sync(input_file, config_arg=None, source_override=None):
    if source_override not in {None, "ipynb", "text"}:
        raise MiniJupyError("invalid source")
    ipynb, py, _ = paired_paths(input_file, config_arg)
    exists_ipynb = Path(ipynb).exists()
    exists_text = Path(py).exists()
    if not Path(input_file).exists():
        raise MiniJupyError("input file does not exist")

    ipynb_model = read_model(ipynb)[0] if exists_ipynb else None
    text_model = read_model(py)[0] if exists_text else None

    if source_override:
        source = source_override
    elif exists_ipynb and not exists_text:
        source = "ipynb"
    elif exists_text and not exists_ipynb:
        source = "text"
    elif version_of(ipynb_model) > version_of(text_model):
        source = "ipynb"
    elif version_of(text_model) > version_of(ipynb_model):
        source = "text"
    else:
        source = "none"

    if source == "none":
        emit({"source": "none", "wrote": [], "version": version_of(ipynb_model), "synced": True})
        return

    source_model = deepcopy(ipynb_model if source == "ipynb" else text_model)
    version = version_of(source_model)
    formats = formats_of(source_model)
    set_minijupy(source_model, formats, version)
    wrote = []

    if source == "ipynb":
        write_text_atomic(py, write_percent(source_model))
        wrote.append(py)
    else:
        out_model = preserve_outputs(source_model, ipynb_model)
        set_minijupy(out_model, formats, version)
        write_json_atomic(ipynb, out_model)
        wrote.append(ipynb)
    emit({"source": source, "wrote": wrote, "version": version, "synced": True})


def main(argv=None):
    parser = argparse.ArgumentParser(prog="minijupy.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect")
    p.add_argument("--input", required=True)
    p.add_argument("--config")

    p = sub.add_parser("to-text")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)

    p = sub.add_parser("to-ipynb")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)

    p = sub.add_parser("pair")
    p.add_argument("--input", required=True)
    p.add_argument("--formats", required=True)
    p.add_argument("--config")

    p = sub.add_parser("sync")
    p.add_argument("--input", required=True)
    p.add_argument("--config")
    p.add_argument("--source")

    p = sub.add_parser("status")
    p.add_argument("--input", required=True)
    p.add_argument("--config")

    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            emit(inspect_model(args.input, args.config))
        elif args.command == "to-text":
            to_text(args.input, args.output)
        elif args.command == "to-ipynb":
            to_ipynb(args.input, args.output)
        elif args.command == "pair":
            pair(args.input, args.formats, args.config)
        elif args.command == "sync":
            sync(args.input, args.config, args.source)
        elif args.command == "status":
            emit(status_report(args.input, args.config))
    except MiniJupyError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import copy
import hashlib
import json
import os
import re
import sys


FORMATS = "ipynb,py:percent"


class MiniError(Exception):
    pass


def rel(path, root):
    return os.path.relpath(os.path.abspath(path), os.path.abspath(root)).replace(os.sep, "/")


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_text(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise MiniError(f"malformed json: {path}") from e


def dump_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def parse_config(path):
    root = os.getcwd() if not path else os.path.dirname(os.path.abspath(path)) or os.getcwd()
    cfg = {"formats": FORMATS, "notebook_dir": None, "script_dir": None, "root": root}
    if not path:
        return cfg
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise MiniError("invalid config")
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k not in {"formats", "notebook_dir", "script_dir"}:
            raise MiniError("invalid config")
        cfg[k] = v
    if cfg["formats"] not in {FORMATS, "py:percent,ipynb"}:
        raise MiniError("invalid config")
    if bool(cfg["notebook_dir"]) != bool(cfg["script_dir"]):
        raise MiniError("invalid config")
    return cfg


def state_path(cfg):
    return os.path.join(cfg["root"], ".minijupy-state.json")


def load_state(cfg):
    path = state_path(cfg)
    if not os.path.exists(path):
        return {"pairs": {}}
    data = load_json(path)
    if not isinstance(data, dict) or "pairs" not in data:
        return {"pairs": {}}
    return data


def save_state(cfg, state):
    dump_json(state_path(cfg), state)


def norm_source(src):
    if src is None:
        return ""
    if isinstance(src, list):
        return "".join(src)
    return str(src)


def normalize_nb(data):
    if not isinstance(data, dict):
        raise MiniError("invalid notebook")
    if data.get("nbformat") != 4:
        raise MiniError("unsupported nbformat")
    nb = {
        "nbformat": 4,
        "nbformat_minor": data.get("nbformat_minor", 5),
        "metadata": {},
        "cells": [],
    }
    md = data.get("metadata") or {}
    if not isinstance(md, dict):
        raise MiniError("invalid metadata")
    if isinstance(md.get("kernelspec"), dict):
        name = md["kernelspec"].get("name")
        nb["metadata"]["kernelspec"] = {"name": name} if name else {}
    elif "kernelspec" in md:
        nb["metadata"]["kernelspec"] = {}
    if isinstance(md.get("language_info"), dict):
        nb["metadata"]["language_info"] = md["language_info"]
    mj = md.get("minijupy") if isinstance(md.get("minijupy"), dict) else {}
    version = mj.get("version", 1)
    if not isinstance(version, int) or version < 0:
        raise MiniError("invalid version")
    minij = {"version": version}
    if "formats" in mj:
        minij["formats"] = mj["formats"]
    nb["metadata"]["minijupy"] = minij
    seen = set()
    for i, c in enumerate(data.get("cells") or [], 1):
        if not isinstance(c, dict):
            raise MiniError("invalid cell")
        ctype = c.get("cell_type")
        if ctype not in {"code", "markdown", "raw"}:
            raise MiniError("unsupported cell type")
        cid = c.get("id") or f"c{i}"
        if cid in seen:
            raise MiniError("duplicate cell id")
        seen.add(cid)
        cm = c.get("metadata") or {}
        keep = {}
        if isinstance(cm, dict):
            if isinstance(cm.get("tags"), list):
                keep["tags"] = [str(x) for x in cm["tags"]]
            if isinstance(cm.get("name"), str):
                keep["name"] = cm["name"]
        cell = {"id": cid, "cell_type": ctype, "source": norm_source(c.get("source")), "metadata": keep}
        if ctype == "code":
            cell["execution_count"] = c.get("execution_count")
            cell["outputs"] = c.get("outputs") if isinstance(c.get("outputs"), list) else []
        nb["cells"].append(cell)
    return nb


def parse_ipynb(path):
    return normalize_nb(load_json(path))


def parse_header(lines):
    md = {}
    i = 0
    if lines and lines[0].strip() == "# ---":
        i = 1
        cur = None
        while i < len(lines):
            line = lines[i].rstrip("\n")
            if line.strip() == "# ---":
                i += 1
                break
            body = line[1:].strip() if line.startswith("#") else line.strip()
            if not body:
                i += 1
                continue
            if body.endswith(":") and not body.startswith(" "):
                cur = body[:-1]
                md.setdefault(cur, {})
            elif ":" in body:
                k, v = body.split(":", 1)
                k = k.strip()
                v = v.strip()
                try:
                    val = int(v)
                except ValueError:
                    val = v
                if cur and line.startswith("#   "):
                    md.setdefault(cur, {})[k] = val
                else:
                    md[k] = val
            i += 1
    return md, i


MARK = re.compile(r"^# %%(?: \[(markdown|md|raw)\])?(?: (\{.*\}))?\s*$")


def parse_percent(path):
    lines = read_text(path).splitlines(True)
    header, i = parse_header(lines)
    cells = []
    cur = None
    body = []
    seen = set()

    def flush():
        nonlocal cur, body
        if cur is None:
            return
        src = "".join(body)
        if cur["cell_type"] == "markdown":
            out = []
            for line in src.splitlines(True):
                out.append(line[2:] if line.startswith("# ") else line)
            src = "".join(out)
        cid = cur.get("id") or f"c{len(cells)+1}"
        if cid in seen:
            raise MiniError("duplicate cell id")
        seen.add(cid)
        meta = {}
        if "tags" in cur:
            meta["tags"] = cur["tags"]
        if "name" in cur:
            meta["name"] = cur["name"]
        cell = {"id": cid, "cell_type": cur["cell_type"], "source": src, "metadata": meta}
        if cur["cell_type"] == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        cells.append(cell)
        cur, body = None, []

    pre = []
    while i < len(lines):
        m = MARK.match(lines[i].rstrip("\n"))
        if m:
            flush()
            typ = m.group(1)
            ctype = "markdown" if typ in {"markdown", "md"} else ("raw" if typ == "raw" else "code")
            meta = {}
            if m.group(2):
                try:
                    meta = json.loads(m.group(2))
                except Exception as e:
                    raise MiniError("malformed marker json") from e
                if not isinstance(meta, dict):
                    raise MiniError("malformed marker json")
            cur = {"cell_type": ctype}
            for k in ["id", "tags", "name"]:
                if k in meta:
                    cur[k] = meta[k]
        else:
            if cur is None:
                pre.append(lines[i])
            else:
                body.append(lines[i])
        i += 1
    if cur is None and any(x.strip() for x in pre):
        cur = {"cell_type": "code"}
        body = pre
    flush()
    version = header.get("minijupy", {}).get("version", 1) if isinstance(header.get("minijupy"), dict) else 1
    if not isinstance(version, int) or version < 0:
        raise MiniError("invalid version")
    meta = {"minijupy": {"version": version}}
    fmts = header.get("minijupy", {}).get("formats") if isinstance(header.get("minijupy"), dict) else None
    if fmts:
        meta["minijupy"]["formats"] = fmts
    kname = header.get("kernelspec", {}).get("name") if isinstance(header.get("kernelspec"), dict) else None
    if kname:
        meta["kernelspec"] = {"name": kname}
    return normalize_nb({"nbformat": 4, "metadata": meta, "cells": cells})


def read_nb(path):
    if path.endswith(".ipynb"):
        return parse_ipynb(path)
    if path.endswith(".py"):
        return parse_percent(path)
    raise MiniError("unsupported file")


def version(nb):
    return nb.get("metadata", {}).get("minijupy", {}).get("version", 1)


def formats(nb):
    return nb.setdefault("metadata", {}).setdefault("minijupy", {}).get("formats")


def set_formats(nb):
    nb.setdefault("metadata", {}).setdefault("minijupy", {})["formats"] = FORMATS


def set_version(nb, v):
    nb.setdefault("metadata", {}).setdefault("minijupy", {})["version"] = v


def stable_token(nb):
    data = copy.deepcopy(nb)
    return hashlib.sha1(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]


def marker(cell):
    typ = cell["cell_type"]
    left = "# %%"
    if typ == "markdown":
        left += " [markdown]"
    elif typ == "raw":
        left += " [raw]"
    meta = {"id": cell.get("id")}
    if cell.get("metadata", {}).get("tags"):
        meta["tags"] = cell["metadata"]["tags"]
    if cell.get("metadata", {}).get("name"):
        meta["name"] = cell["metadata"]["name"]
    return left + " " + json.dumps(meta, separators=(",", ":")) + "\n"


def percent_text(nb):
    mj = nb.get("metadata", {}).get("minijupy", {})
    out = ["# ---\n", "# minijupy:\n", f"#   formats: {mj.get('formats', FORMATS)}\n", f"#   version: {mj.get('version', 1)}\n"]
    kname = nb.get("metadata", {}).get("kernelspec", {}).get("name")
    if kname:
        out += ["# kernelspec:\n", f"#   name: {kname}\n"]
    out.append("# ---\n")
    for c in nb["cells"]:
        out.append(marker(c))
        src = c.get("source", "")
        if c["cell_type"] == "markdown":
            for line in src.splitlines(True):
                out.append("# " + line if line.strip() else "#\n")
        else:
            out.append(src)
        if out and not out[-1].endswith("\n"):
            out.append("\n")
    return "".join(out)


def ipynb_obj(nb, keep_outputs=True):
    data = copy.deepcopy(nb)
    for c in data["cells"]:
        if c["cell_type"] != "code":
            c.pop("execution_count", None)
            c.pop("outputs", None)
        elif not keep_outputs:
            c["execution_count"] = None
            c["outputs"] = []
    return data


def write_ipynb(path, nb):
    dump_json(path, ipynb_obj(nb, True))


def write_percent(path, nb):
    write_text(path, percent_text(nb))


def pair_paths(path, cfg):
    root = cfg["root"]
    rp = rel(path, root)
    nd, sd = cfg.get("notebook_dir"), cfg.get("script_dir")
    if nd and sd:
        nd = nd.strip("/")
        sd = sd.strip("/")
        if rp.startswith(nd + "/") and rp.endswith(".ipynb"):
            stem = rp[len(nd)+1:-6]
            return rp, f"{sd}/{stem}.py"
        if rp.startswith(sd + "/") and rp.endswith(".py"):
            stem = rp[len(sd)+1:-3]
            return f"{nd}/{stem}.ipynb", rp
        raise MiniError("path mismatch")
    base, ext = os.path.splitext(rp)
    if ext == ".ipynb":
        return rp, base + ".py"
    if ext == ".py":
        return base + ".ipynb", rp
    raise MiniError("path mismatch")


def abs_pair(ipynb_rel, text_rel, cfg):
    return os.path.join(cfg["root"], ipynb_rel), os.path.join(cfg["root"], text_rel)


def pair_status(ipynb_rel, text_rel, cfg):
    ip, tx = abs_pair(ipynb_rel, text_rel, cfg)
    state = load_state(cfg)
    entry = state.get("pairs", {}).get(ipynb_rel, {})
    exists = {"ipynb": os.path.exists(ip), "text": os.path.exists(tx)}
    ip_nb = read_nb(ip) if exists["ipynb"] else None
    tx_nb = read_nb(tx) if exists["text"] else None
    iv = version(ip_nb) if ip_nb else None
    tv = version(tx_nb) if tx_nb else None
    last = entry.get("last_synced", {})
    li = last.get("ipynb_version")
    lt = last.get("text_version")
    missing = []
    if not exists["ipynb"]:
        missing.append(ipynb_rel)
    if not exists["text"]:
        missing.append(text_rel)
    conflict = False
    source = "none"
    if exists["ipynb"] and exists["text"] and li is not None and lt is not None:
        ich = iv > li
        tch = tv > lt
        if ich and tch:
            conflict = True
            source = "none"
        elif ich:
            source = "ipynb"
        elif tch:
            source = "text"
    elif exists["ipynb"] and not exists["text"]:
        source = "ipynb"
    elif exists["text"] and not exists["ipynb"]:
        source = "text"
    elif exists["ipynb"] and exists["text"]:
        source = "none"
    planned = []
    if not conflict:
        if source == "ipynb":
            planned = [text_rel, ".minijupy-state.json"]
        elif source == "text":
            planned = [ipynb_rel, ".minijupy-state.json"]
    roundtrip_ok = not missing and not conflict
    diffs = []
    if li is not None and iv is not None and li > iv or lt is not None and tv is not None and lt > tv:
        roundtrip_ok = False
        diffs.append("state")
    return {
        "ipynb": ipynb_rel, "text": text_rel, "exists": exists,
        "versions": {"ipynb": iv, "text": tv, "last_ipynb": li, "last_text": lt},
        "source": source, "conflict": conflict, "missing": missing,
        "planned_writes": planned, "roundtrip_ok": roundtrip_ok, "differences": diffs, "errors": []
    }


def status_obj(command, pairs, cfg):
    conflicts = sum(1 for p in pairs if p["conflict"])
    missing = sum(1 for p in pairs if p["missing"])
    errors = sum(1 for p in pairs if p["errors"])
    planned = sum(len(p["planned_writes"]) for p in pairs)
    return {"ok": errors == 0, "command": command, "root": ".", "pairs": pairs,
            "summary": {"pairs": len(pairs), "conflicts": conflicts, "missing": missing, "planned_writes": planned, "errors": errors}}


def discover_pairs(cfg):
    root = cfg["root"]
    pairs = {}
    nd, sd = cfg.get("notebook_dir"), cfg.get("script_dir")
    dirs = [nd, sd] if nd and sd else ["."]
    for d in dirs:
        base = os.path.join(root, d)
        if not os.path.isdir(base):
            continue
        for cur, _, files in os.walk(base):
            for f in files:
                if f.endswith((".ipynb", ".py")):
                    ip, tx = pair_paths(os.path.join(cur, f), cfg)
                    pairs[ip] = tx
    for ip, ent in load_state(cfg).get("pairs", {}).items():
        pairs.setdefault(ip, ent.get("text"))
    return sorted(pairs.items())


def preserve_outputs(text_nb, ip_nb):
    old = ip_nb["cells"]
    used = set()
    newcells = []
    for pos, cell in enumerate(text_nb["cells"]):
        cell = copy.deepcopy(cell)
        match = None
        for i, oc in enumerate(old):
            if i not in used and oc.get("id") == cell.get("id"):
                match = i; break
        if match is None:
            h = hashlib.sha1(cell.get("source", "").encode()).hexdigest()
            for i, oc in enumerate(old):
                oh = hashlib.sha1(oc.get("source", "").encode()).hexdigest()
                if i not in used and oc.get("cell_type") == cell.get("cell_type") and oh == h:
                    match = i; break
        if match is None and pos < len(old) and pos not in used and old[pos].get("cell_type") == cell.get("cell_type"):
            match = pos
        if cell["cell_type"] == "code":
            if match is not None:
                used.add(match)
                cell["execution_count"] = old[match].get("execution_count")
                cell["outputs"] = copy.deepcopy(old[match].get("outputs", []))
            else:
                cell["execution_count"] = None
                cell["outputs"] = []
        newcells.append(cell)
    text_nb["cells"] = newcells
    return text_nb


def update_state(cfg, ipynb_rel, text_rel, ip_nb, tx_nb):
    st = load_state(cfg)
    st.setdefault("pairs", {})[ipynb_rel] = {
        "ipynb": ipynb_rel, "text": text_rel,
        "last_synced": {
            "ipynb_version": version(ip_nb), "text_version": version(tx_nb),
            "ipynb_hash": stable_token(ip_nb), "text_hash": stable_token(tx_nb)
        }
    }
    save_state(cfg, st)


def do_pair(args, cfg):
    ipr, txr = pair_paths(args.input, cfg)
    ip, tx = abs_pair(ipr, txr, cfg)
    if os.path.exists(ip):
        nb = read_nb(ip)
        set_formats(nb)
        write_ipynb(ip, nb)
        if os.path.exists(tx):
            tnb = read_nb(tx)
            set_formats(tnb)
        else:
            tnb = copy.deepcopy(nb)
            write_percent(tx, tnb)
    elif os.path.exists(tx):
        tnb = read_nb(tx)
        set_formats(tnb)
        nb = ipynb_obj(tnb, False)
        nb = normalize_nb(nb)
        write_ipynb(ip, nb)
    else:
        raise MiniError("missing pair")
    ipnb, txnb = read_nb(ip), read_nb(tx)
    update_state(cfg, ipr, txr, ipnb, txnb)
    return status_obj("pair", [pair_status(ipr, txr, cfg)], cfg)


def do_sync_one(ipr, txr, cfg, source=None, write=True):
    st = pair_status(ipr, txr, cfg)
    if st["conflict"] and not source:
        raise MiniError("conflict")
    src = source or st["source"]
    ip, tx = abs_pair(ipr, txr, cfg)
    if src == "none":
        return st
    if src == "ipynb":
        nb = read_nb(ip)
        set_formats(nb)
        write_percent(tx, nb)
        txnb = read_nb(tx)
        update_state(cfg, ipr, txr, nb, txnb)
    elif src == "text":
        tnb = read_nb(tx)
        set_formats(tnb)
        if os.path.exists(ip):
            inb = read_nb(ip)
            tnb = preserve_outputs(tnb, inb)
        set_version(tnb, version(tnb))
        write_ipynb(ip, tnb)
        update_state(cfg, ipr, txr, read_nb(ip), read_nb(tx))
    return pair_status(ipr, txr, cfg)


def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ["inspect", "to-text", "to-ipynb", "pair", "status", "check", "sync"]:
        sp = sub.add_parser(name)
        sp.add_argument("--input")
        sp.add_argument("--output")
        sp.add_argument("--config")
        sp.add_argument("--all", action="store_true")
        sp.add_argument("--source", choices=["ipynb", "text"])
    args = p.parse_args(argv)
    cfg = parse_config(args.config)
    try:
        if args.cmd == "inspect":
            nb = read_nb(args.input)
            print(json.dumps({"ok": True, "command": "inspect", "path": rel(args.input, cfg["root"]), "format": "ipynb" if args.input.endswith(".ipynb") else "py:percent", "version": version(nb), "notebook": nb}, sort_keys=True))
        elif args.cmd == "to-text":
            if not args.input.endswith(".ipynb") or not args.output.endswith(".py"):
                raise MiniError("invalid conversion")
            nb = read_nb(args.input); write_percent(args.output, nb)
            print(json.dumps({"ok": True, "command": "to-text", "output": rel(args.output, cfg["root"])}))
        elif args.cmd == "to-ipynb":
            if not args.input.endswith(".py") or not args.output.endswith(".ipynb"):
                raise MiniError("invalid conversion")
            nb = read_nb(args.input); write_ipynb(args.output, nb)
            print(json.dumps({"ok": True, "command": "to-ipynb", "output": rel(args.output, cfg["root"])}))
        elif args.cmd == "pair":
            print(json.dumps(do_pair(args, cfg), sort_keys=True))
        elif args.cmd in {"status", "check"}:
            if args.all:
                pairs = [pair_status(ip, tx, cfg) for ip, tx in discover_pairs(cfg)]
            else:
                ip, tx = pair_paths(args.input, cfg)
                pairs = [pair_status(ip, tx, cfg)]
            obj = status_obj(args.cmd, pairs, cfg)
            if args.cmd == "check":
                for pair in obj["pairs"]:
                    if pair["differences"]:
                        pair["roundtrip_ok"] = False
            print(json.dumps(obj, sort_keys=True))
        elif args.cmd == "sync":
            if args.all:
                planned = [(ip, tx, pair_status(ip, tx, cfg)) for ip, tx in discover_pairs(cfg)]
                for _, _, st in planned:
                    if st["conflict"] and not args.source:
                        raise MiniError("conflict")
                    if st["errors"]:
                        raise MiniError("errors")
                pairs = [do_sync_one(ip, tx, cfg, args.source) for ip, tx, _ in planned]
            else:
                ip, tx = pair_paths(args.input, cfg)
                pairs = [do_sync_one(ip, tx, cfg, args.source)]
            print(json.dumps(status_obj("sync", pairs, cfg), sort_keys=True))
    except MiniError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUBRIC = ROOT / "task" / "jupytext-realrepo-002" / "rubric.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_setup(work, files):
    for name, content in files.items():
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def as_command(item):
    if isinstance(item, list):
        return item, False
    return item["args"], bool(item.get("expect_error"))


def run_case(case, program):
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        write_setup(work, case.get("setup_files", {}))
        results = []
        passed = True
        diagnostics = []
        for idx, item in enumerate(case.get("commands", [])):
            args, expect_error = as_command(item)
            proc = subprocess.run([sys.executable, str(program), *args], cwd=work, text=True, capture_output=True, timeout=10)
            ok = proc.returncode != 0 if expect_error else proc.returncode == 0
            if not ok:
                passed = False
                diagnostics.append(f"command {idx} exit {proc.returncode}, expect_error={expect_error}, stderr={proc.stderr.strip()}")
            stdout_json = None
            if proc.stdout.strip():
                try:
                    stdout_json = json.loads(proc.stdout)
                except Exception:
                    stdout_json = None
            results.append({"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "json": stdout_json})
        checks = case.get("checks", {})
        try:
            check_all(work, results, checks)
        except AssertionError as e:
            passed = False
            diagnostics.append(str(e))
        return passed, diagnostics


def contains(actual, expected):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for k, v in expected.items():
            if k not in actual or not contains(actual[k], v):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        if len(expected) > len(actual):
            return False
        used = set()
        for exp in expected:
            found = False
            for i, act in enumerate(actual):
                if i not in used and contains(act, exp):
                    used.add(i)
                    found = True
                    break
            if not found:
                return False
        return True
    return actual == expected


def not_contains(actual, expected):
    if contains(actual, expected):
        return False
    if isinstance(actual, dict):
        return all(not_contains(v, expected) for v in actual.values())
    if isinstance(actual, list):
        return all(not_contains(v, expected) for v in actual)
    return True


def read_file_json(work, rel):
    path = work / rel
    if not path.exists():
        raise AssertionError(f"missing json file {rel}")
    return json.loads(path.read_text(encoding="utf-8"))


def check_all(work, results, checks):
    for rel in checks.get("file_exists", []):
        assert (work / rel).exists(), f"expected file exists: {rel}"
    for rel in checks.get("file_not_exists", []):
        assert not (work / rel).exists(), f"expected file not exists: {rel}"
    for rel, needles in checks.get("file_contains", {}).items():
        text = (work / rel).read_text(encoding="utf-8")
        for n in needles:
            assert n in text, f"{rel} missing substring {n!r}"
    for rel, needles in checks.get("file_not_contains", {}).items():
        text = (work / rel).read_text(encoding="utf-8") if (work / rel).exists() else ""
        for n in needles:
            assert n not in text, f"{rel} unexpectedly contains {n!r}"
    for rel, exp in checks.get("file_json_contains_unordered", {}).items():
        actual = read_file_json(work, rel)
        assert contains(actual, exp), f"{rel} json does not contain {exp!r}; got {actual!r}"
    for idx, exp in checks.get("stdout_json_contains", {}).items():
        actual = results[int(idx)]["json"]
        assert actual is not None, f"stdout {idx} is not json: {results[int(idx)]['stdout']!r}"
        assert contains(actual, exp), f"stdout {idx} json does not contain {exp!r}; got {actual!r}"


def score(program, report_path=None):
    cases = load_json(RUBRIC)
    passed = []
    failed = []
    for case in cases:
        ok, diag = run_case(case, program)
        rec = {"id": case["id"], "layer": case["layer"], "passed": ok, "diagnostics": diag}
        (passed if ok else failed).append(rec)
    unit_total = sum(1 for c in cases if c["layer"] == "unit")
    sys_total = sum(1 for c in cases if c["layer"] == "system")
    unit_pass = sum(1 for r in passed if r["layer"] == "unit")
    sys_pass = sum(1 for r in passed if r["layer"] == "system")
    result = {
        "program": str(program),
        "total_cases": len(cases),
        "unit_pass": unit_pass,
        "unit_total": unit_total,
        "system_pass": sys_pass,
        "system_total": sys_total,
        "unit_score": round(100 * unit_pass / unit_total, 2),
        "system_score": round(100 * sys_pass / sys_total, 2),
        "gap_pp": round(100 * unit_pass / unit_total - 100 * sys_pass / sys_total, 2),
        "failed_case_ids": [r["id"] for r in failed],
        "failed": failed,
    }
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("program")
    ap.add_argument("--report")
    args = ap.parse_args()
    res = score(Path(args.program).resolve(), args.report)
    print(json.dumps(res, indent=2))
    return 0 if not res["failed_case_ids"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

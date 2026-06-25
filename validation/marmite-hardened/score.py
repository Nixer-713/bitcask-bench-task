#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text())


def compact_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def subset(actual, expected):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(k in actual and subset(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        used = set()
        for exp in expected:
            match = None
            for idx, act in enumerate(actual):
                if idx not in used and subset(act, exp):
                    match = idx
                    break
            if match is None:
                return False
            used.add(match)
        return True
    return actual == expected


def get_path(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def write_setup(root, files):
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def run_case(program, case, rubric_root):
    with tempfile.TemporaryDirectory(prefix=f"{case['id']}_") as td:
        root = Path(td)
        write_setup(root, case.get("setup_files", {}))
        outputs = []
        diagnostics = []
        for command in case.get("commands", []):
            if isinstance(command, list):
                args = command
                expect_error = False
            else:
                args = command["args"]
                expect_error = command.get("expect_error", False)
            proc = subprocess.run(
                [sys.executable, str(program), *args],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
            if expect_error:
                if proc.returncode == 0:
                    diagnostics.append(f"expected failure for {args}, got exit 0")
            elif proc.returncode != 0:
                diagnostics.append(f"command {args} failed: {proc.stderr.strip()}")
            parsed = None
            if proc.stdout.strip():
                try:
                    parsed = json.loads(proc.stdout)
                except json.JSONDecodeError:
                    diagnostics.append(f"stdout is not JSON for {args}: {proc.stdout!r}")
            outputs.append({"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode, "json": parsed})
        checks = case.get("checks", {})
        for rel in checks.get("file_exists", []):
            if not (root / rel).exists():
                diagnostics.append(f"missing file {rel}")
        for rel in checks.get("file_not_exists", []):
            if (root / rel).exists():
                diagnostics.append(f"unexpected file {rel}")
        for rel, needles in checks.get("file_contains", {}).items():
            path = root / rel
            if not path.exists():
                diagnostics.append(f"missing file for contains {rel}")
                continue
            text = path.read_text()
            for needle in needles:
                if needle not in text:
                    diagnostics.append(f"{rel} missing text {needle!r}")
        for rel, needles in checks.get("file_not_contains", {}).items():
            path = root / rel
            if not path.exists():
                diagnostics.append(f"missing file for not_contains {rel}")
                continue
            text = path.read_text()
            for needle in needles:
                if needle in text:
                    diagnostics.append(f"{rel} unexpectedly contains text {needle!r}")
        for idx, expected in checks.get("stdout_json_contains_unordered", {}).items():
            actual = outputs[int(idx)]["json"]
            if not subset(actual, expected):
                diagnostics.append(f"stdout {idx} does not contain expected subset")
        for idx, rel in checks.get("stdout_json_equals_file_json", {}).items():
            actual = outputs[int(idx)]["json"]
            path = root / rel
            if not path.exists():
                diagnostics.append(f"missing JSON file for stdout comparison {rel}")
                continue
            expected = json.loads(path.read_text())
            if actual != expected:
                diagnostics.append(f"stdout {idx} JSON != {rel}")
        for path_expr, expected in checks.get("stdout_json_path_length", {}).items():
            idx, dotted = path_expr.split(".", 1)
            actual = get_path(outputs[int(idx)]["json"], dotted)
            if len(actual) != expected:
                diagnostics.append(f"{path_expr} length {len(actual)} != {expected}")
        for path_expr, expected in checks.get("stdout_json_path_equals", {}).items():
            idx, dotted = path_expr.split(".", 1)
            actual = get_path(outputs[int(idx)]["json"], dotted)
            if actual != expected:
                diagnostics.append(f"{path_expr} {actual!r} != {expected!r}")
        for rel, expected in checks.get("file_json_contains_unordered", {}).items():
            path = root / rel
            if not path.exists():
                diagnostics.append(f"missing JSON file {rel}")
                continue
            actual = json.loads(path.read_text())
            if not subset(actual, expected):
                diagnostics.append(f"{rel} does not contain expected JSON subset")
        for rel, banned in checks.get("file_json_not_contains", {}).items():
            path = root / rel
            if not path.exists():
                diagnostics.append(f"missing JSON file {rel}")
                continue
            text = compact_text(json.loads(path.read_text()))
            for needle in banned:
                if needle in text:
                    diagnostics.append(f"{rel} unexpectedly contains {needle!r}")
        return not diagnostics, diagnostics


def score(program, rubric):
    results = []
    for case in rubric:
        ok, diagnostics = run_case(Path(program).resolve(), case, Path.cwd())
        results.append({**case, "passed": ok, "diagnostics": diagnostics})
    unit_cases = [r for r in results if r["layer"] == "unit"]
    system_cases = [r for r in results if r["layer"] == "system"]
    unit_pass = sum(r["passed"] for r in unit_cases)
    system_pass = sum(r["passed"] for r in system_cases)
    unit_score = 100.0 * unit_pass / len(unit_cases)
    system_score = 100.0 * system_pass / len(system_cases)
    return {
        "unit_pass": unit_pass,
        "unit_total": len(unit_cases),
        "system_pass": system_pass,
        "system_total": len(system_cases),
        "unit_score": unit_score,
        "system_score": system_score,
        "gap_pp": unit_score - system_score,
        "failed_case_ids": [r["id"] for r in results if not r["passed"]],
        "cases": [{"id": r["id"], "layer": r["layer"], "passed": r["passed"], "diagnostics": r["diagnostics"]} for r in results],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", required=True)
    ap.add_argument("--rubric", default="task/marmite-realrepo-001/rubric.json")
    ap.add_argument("--out")
    args = ap.parse_args()
    result = score(args.program, load_json(args.rubric))
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n")
    print(text)
    return 0 if not result["failed_case_ids"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

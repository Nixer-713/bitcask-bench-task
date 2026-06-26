#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUBRIC = ROOT / "task/jupytext-realrepo-001/rubric.json"


def load_json(path):
    return json.loads(Path(path).read_text())


def as_list(value):
    return value if isinstance(value, list) else [value]


def contains_subset(actual, expected):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, value in expected.items():
            if key not in actual or not contains_subset(actual[key], value):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        used = set()
        for exp_item in expected:
            matched = False
            for idx, act_item in enumerate(actual):
                if idx in used:
                    continue
                if contains_subset(act_item, exp_item):
                    used.add(idx)
                    matched = True
                    break
            if not matched:
                return False
        return True
    return actual == expected


def json_from_stdout(result):
    text = result["stdout"].strip()
    if not text:
        raise AssertionError("stdout is empty")
    return json.loads(text.splitlines()[-1])


def run_command(solution, cwd, command):
    expect_error = False
    if isinstance(command, dict):
        args = command["args"]
        expect_error = bool(command.get("expect_error"))
    else:
        args = command
    proc = subprocess.run(
        [sys.executable, str(solution), *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    if expect_error and proc.returncode == 0:
        raise AssertionError(f"expected error but command succeeded: {args}")
    if not expect_error and proc.returncode != 0:
        raise AssertionError(f"command failed {args}: {proc.stderr.strip()}")
    return {
        "args": args,
        "expect_error": expect_error,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def write_setup(root, setup_files):
    for rel, content in (setup_files or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def check_stdout_json_contains(results, expected):
    for index, subset in expected.items():
        actual = json_from_stdout(results[int(index)])
        if not contains_subset(actual, subset):
            raise AssertionError(f"stdout JSON for command {index} missing subset {subset!r}; actual={actual!r}")


def check_file_json_contains(root, expected):
    for rel, subset in expected.items():
        path = root / rel
        if not path.exists():
            raise AssertionError(f"missing JSON file {rel}")
        actual = json.loads(path.read_text())
        if not contains_subset(actual, subset):
            raise AssertionError(f"{rel} missing subset {subset!r}; actual={actual!r}")


def check_file_contains(root, expected):
    for rel, needles in expected.items():
        path = root / rel
        if not path.exists():
            raise AssertionError(f"missing file {rel}")
        text = path.read_text()
        for needle in as_list(needles):
            if needle not in text:
                raise AssertionError(f"{rel} does not contain {needle!r}")


def check_file_not_contains(root, expected):
    for rel, needles in expected.items():
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text()
        for needle in as_list(needles):
            if needle in text:
                raise AssertionError(f"{rel} unexpectedly contains {needle!r}")


def check_exists(root, expected, should_exist):
    for rel in as_list(expected):
        exists = (root / rel).exists()
        if should_exist and not exists:
            raise AssertionError(f"expected file to exist: {rel}")
        if not should_exist and exists:
            raise AssertionError(f"expected file not to exist: {rel}")


def run_checks(root, results, checks):
    for kind, expected in (checks or {}).items():
        if kind == "stdout_json_contains_unordered":
            check_stdout_json_contains(results, expected)
        elif kind == "file_json_contains_unordered":
            check_file_json_contains(root, expected)
        elif kind == "file_contains":
            check_file_contains(root, expected)
        elif kind == "file_not_contains":
            check_file_not_contains(root, expected)
        elif kind == "file_exists":
            check_exists(root, expected, True)
        elif kind == "file_not_exists":
            check_exists(root, expected, False)
        else:
            raise AssertionError(f"unsupported check type: {kind}")


def score_case(case, solution):
    with tempfile.TemporaryDirectory(prefix=f"{case['id']}_") as td:
        work = Path(td)
        write_setup(work, case.get("setup_files", {}))
        results = []
        for command in case.get("commands", []):
            results.append(run_command(solution, work, command))
        run_checks(work, results, case.get("checks", {}))
    return results


def summarize(case_results):
    unit_total = sum(1 for r in case_results if r["layer"] == "unit")
    system_total = sum(1 for r in case_results if r["layer"] == "system")
    unit_pass = sum(1 for r in case_results if r["layer"] == "unit" and r["passed"])
    system_pass = sum(1 for r in case_results if r["layer"] == "system" and r["passed"])
    unit_score = 100.0 * unit_pass / unit_total if unit_total else 0.0
    system_score = 100.0 * system_pass / system_total if system_total else 0.0
    return {
        "total_cases": len(case_results),
        "unit_pass": unit_pass,
        "unit_total": unit_total,
        "system_pass": system_pass,
        "system_total": system_total,
        "unit_score": round(unit_score, 2),
        "system_score": round(system_score, 2),
        "gap_pp": round(unit_score - system_score, 2),
        "failed_case_ids": [r["id"] for r in case_results if not r["passed"]],
    }


def score(solution, rubric_path):
    solution = Path(solution).resolve()
    rubric = load_json(rubric_path)
    case_results = []
    for case in rubric:
        result = {
            "id": case["id"],
            "layer": case["layer"],
            "system_dimension": case.get("system_dimension"),
            "passed": False,
            "error": None,
        }
        try:
            score_case(case, solution)
            result["passed"] = True
        except Exception as exc:
            result["error"] = str(exc)
        case_results.append(result)
    return {"summary": summarize(case_results), "cases": case_results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True)
    parser.add_argument("--rubric", default=str(DEFAULT_RUBRIC))
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    report = score(args.solution, args.rubric)
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report["summary"], separators=(",", ":")))
    raise SystemExit(0 if not report["summary"]["failed_case_ids"] else 1)


if __name__ == "__main__":
    main()

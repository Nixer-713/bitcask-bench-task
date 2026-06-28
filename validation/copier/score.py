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
RUBRIC = ROOT / "task/copier-realrepo-001/rubric.json"


def write_file(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def setup_git_repo(work, rel, commits):
    repo = work / rel
    repo.mkdir(parents=True, exist_ok=True)
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "bench@example.com"], repo)
    run(["git", "config", "user.name", "Bench"], repo)
    for item in commits:
        for child in list(repo.iterdir()):
            if child.name == ".git":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        for path, content in item.get("files", {}).items():
            write_file(repo, path, content)
        res = run(["git", "add", "."], repo)
        if res.returncode != 0:
            raise RuntimeError(res.stderr)
        res = run(["git", "commit", "-m", item["tag"]], repo)
        if res.returncode != 0:
            raise RuntimeError(res.stderr)
        res = run(["git", "tag", item["tag"]], repo)
        if res.returncode != 0:
            raise RuntimeError(res.stderr)


def contains_subset(actual, expected):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, val in expected.items():
            if key not in actual or not contains_subset(actual[key], val):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        for item in expected:
            if item not in actual:
                return False
        return True
    return actual == expected


def check_file_contains(work, checks, failures, negate=False):
    for rel, needles in checks.items():
        path = work / rel
        if not path.exists():
            failures.append(f"{rel} missing")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            present = needle in text
            if negate and present:
                failures.append(f"{rel} unexpectedly contains {needle!r}")
            elif not negate and not present:
                failures.append(f"{rel} missing content {needle!r}")


def evaluate_case(case, entrypoint):
    work = Path(tempfile.mkdtemp(prefix=f"copier-{case['id']}-"))
    outputs = []
    failures = []
    try:
        for rel, content in case.get("setup_files", {}).items():
            write_file(work, rel, content)
        for rel, commits in (case.get("setup_git") or {}).items():
            setup_git_repo(work, rel, commits)
        for step in case.get("steps", []):
            if "write_file" in step:
                wf = step["write_file"]
                write_file(work, wf["path"], wf["content"])
                outputs.append({"kind": "write_file", "returncode": 0, "stdout": "", "stderr": ""})
                continue
            args = step.get("args", [])
            res = run([sys.executable, str(entrypoint), *args], work)
            outputs.append({"kind": "command", "returncode": res.returncode, "stdout": res.stdout, "stderr": res.stderr})
            expect_error = step.get("expect_error", False)
            if expect_error and res.returncode == 0:
                failures.append(f"step {len(outputs)-1} expected error but exited 0")
            if not expect_error and res.returncode != 0:
                failures.append(f"step {len(outputs)-1} failed rc={res.returncode} stderr={res.stderr.strip()}")
        checks = case.get("checks", {})
        for rel in checks.get("file_exists", []):
            if not (work / rel).exists():
                failures.append(f"{rel} does not exist")
        for rel in checks.get("file_not_exists", []):
            if (work / rel).exists():
                failures.append(f"{rel} unexpectedly exists")
        check_file_contains(work, checks.get("file_contains", {}), failures, negate=False)
        check_file_contains(work, checks.get("file_contains_any_order", {}), failures, negate=False)
        check_file_contains(work, checks.get("file_not_contains", {}), failures, negate=True)
        for index, expected in checks.get("stdout_json_contains", {}).items():
            i = int(index)
            if i >= len(outputs):
                failures.append(f"stdout step {i} missing")
                continue
            try:
                actual = json.loads(outputs[i]["stdout"])
            except Exception as exc:
                failures.append(f"stdout step {i} is not json: {exc}; stdout={outputs[i]['stdout']!r}")
                continue
            if not contains_subset(actual, expected):
                failures.append(f"stdout step {i} missing subset {expected!r}; actual={actual!r}")
        passed = not failures
        return {
            "id": case["id"],
            "layer": case["layer"],
            "category": case.get("category"),
            "system_dimension": case.get("system_dimension"),
            "requirement_refs": case.get("requirement_refs", []),
            "weight": case.get("weight", 1),
            "passed": passed,
            "failure_reason": "; ".join(failures),
            "outputs": outputs,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def score(entrypoint, report_path=None):
    cases = json.loads(RUBRIC.read_text())
    results = [evaluate_case(case, entrypoint) for case in cases]
    unit = [r for r in results if r["layer"] == "unit"]
    system = [r for r in results if r["layer"] == "system"]
    summary = {
        "entrypoint": str(entrypoint),
        "total_cases": len(results),
        "unit_passed": sum(r["passed"] for r in unit),
        "unit_total": len(unit),
        "system_passed": sum(r["passed"] for r in system),
        "system_total": len(system),
        "total_passed": sum(r["passed"] for r in results),
        "failed_case_ids": [r["id"] for r in results if not r["passed"]],
        "unit_score": 100.0 * sum(r["passed"] for r in unit) / len(unit),
        "system_score": 100.0 * sum(r["passed"] for r in system) / len(system),
    }
    summary["gap_pp"] = summary["unit_score"] - summary["system_score"]
    report = {"summary": summary, "cases": results}
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrypoint")
    ap.add_argument("--report")
    args = ap.parse_args()
    report = score(Path(args.entrypoint).resolve(), args.report)
    print(json.dumps(report["summary"], indent=2))
    raise SystemExit(0 if not report["summary"]["failed_case_ids"] else 1)


if __name__ == "__main__":
    main()

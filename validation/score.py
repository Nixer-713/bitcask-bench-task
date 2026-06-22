#!/usr/bin/env python3
"""Score a kvmini.py implementation against task/bitcask-realrepo-001/rubric.json."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def norm_command(item: Any) -> tuple[list[str], bool]:
    if isinstance(item, dict):
        return list(item["args"]), bool(item.get("expect_error", False))
    return list(item), False


def json_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and json_subset(value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and all(
            any(json_subset(exp_item, act_item) for act_item in actual)
            for exp_item in expected
        )
    return expected == actual


def check_stdout_equals(outputs: list[str], spec: dict[str, Any], errors: list[str]) -> None:
    for index, expected in spec.items():
        got = outputs[int(index)].strip()
        if got != str(expected):
            errors.append(f"cmd{index} stdout_equals expected {expected!r}, got {got!r}")


def check_stdout_json(
    outputs: list[str],
    spec: dict[str, Any],
    errors: list[str],
    subset: bool = False,
) -> None:
    for index, expected in spec.items():
        raw = outputs[int(index)].strip()
        try:
            actual = json.loads(raw)
        except json.JSONDecodeError:
            errors.append(f"cmd{index} stdout_json invalid JSON: {raw!r}")
            continue
        ok = json_subset(expected, actual) if subset else expected == actual
        if not ok:
            errors.append(f"cmd{index} stdout_json expected {expected!r}, got {actual!r}")


def run_case(case: dict[str, Any], solution: Path) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        for name, content in case.get("setup_files", {}).items():
            target = workspace / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        env = os.environ.copy()
        env.update({key: str(value) for key, value in case.get("env", {}).items()})
        commands = [norm_command(item) for item in case["commands"]]
        outputs: list[str] = []

        for index, (args, expect_error) in enumerate(commands):
            proc = subprocess.run(
                [sys.executable, str(solution), *args],
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            outputs.append(proc.stdout)
            if expect_error and proc.returncode == 0:
                errors.append(f"cmd{index} expected nonzero exit, got 0")
            if not expect_error and proc.returncode != 0:
                errors.append(
                    f"cmd{index} expected success, got {proc.returncode}: "
                    f"{proc.stderr.strip()!r}"
                )

        checks = case.get("checks", {})
        if "stdout_equals" in checks:
            check_stdout_equals(outputs, checks["stdout_equals"], errors)
        if "stdout_json" in checks:
            check_stdout_json(outputs, checks["stdout_json"], errors)
        if "stdout_json_contains" in checks:
            check_stdout_json(outputs, checks["stdout_json_contains"], errors, subset=True)

    return errors


def bucket_score(weight: int, passed_weight: int, cases: int, passed_cases: int) -> dict[str, Any]:
    return {
        "weight": weight,
        "passed_weight": passed_weight,
        "cases": cases,
        "passed_cases": passed_cases,
        "score": round(passed_weight / weight, 4) if weight else 0.0,
    }


def aggregate(cases: list[dict[str, Any]], results: list[list[str]], label: str) -> dict[str, Any]:
    layer_totals: dict[str, dict[str, int]] = {}
    dim_totals: dict[str, dict[str, int]] = {}
    failed_cases: list[dict[str, Any]] = []
    all_cases: list[dict[str, Any]] = []
    total_weight = 0
    passed_weight = 0

    def acc(store: dict[str, dict[str, int]], key: str, weight: int, passed: bool) -> None:
        item = store.setdefault(key, {"weight": 0, "passed_weight": 0, "cases": 0, "passed_cases": 0})
        item["weight"] += weight
        item["cases"] += 1
        if passed:
            item["passed_weight"] += weight
            item["passed_cases"] += 1

    for case, errors in zip(cases, results):
        passed = not errors
        weight = int(case["weight"])
        total_weight += weight
        if passed:
            passed_weight += weight
        acc(layer_totals, case["layer"], weight, passed)
        if case["layer"] == "system":
            acc(dim_totals, case["system_dimension"], weight, passed)
        entry = {
            "id": case["id"],
            "layer": case["layer"],
            "category": case["category"],
            "weight": weight,
            "passed": passed,
        }
        if case["layer"] == "system":
            entry["system_dimension"] = case["system_dimension"]
        if errors:
            entry["errors"] = errors
            failed_cases.append(entry)
        all_cases.append(entry)

    layers = {
        key: bucket_score(value["weight"], value["passed_weight"], value["cases"], value["passed_cases"])
        for key, value in layer_totals.items()
    }
    system_dimensions = {
        key: bucket_score(value["weight"], value["passed_weight"], value["cases"], value["passed_cases"])
        for key, value in dim_totals.items()
    }
    unit = layers.get("unit", bucket_score(0, 0, 0, 0))
    system = layers.get("system", bucket_score(0, 0, 0, 0))

    return {
        "label": label,
        "total_cases": len(cases),
        "passed_cases": sum(1 for errors in results if not errors),
        "total_weight": total_weight,
        "passed_weight": passed_weight,
        "score": round(passed_weight / total_weight, 4) if total_weight else 0.0,
        "unit_score": unit,
        "system_score": system,
        "gap_pp": round((unit["score"] - system["score"]) * 100, 2),
        "system_dimensions": system_dimensions,
        "failed_cases": failed_cases,
        "all_cases": all_cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True)
    parser.add_argument("--rubric", default="task/bitcask-realrepo-001/rubric.json")
    parser.add_argument("--label", default="solution")
    parser.add_argument("--out")
    args = parser.parse_args()

    solution = Path(args.solution).resolve()
    rubric = Path(args.rubric)
    cases = json.loads(rubric.read_text(encoding="utf-8"))
    results = [run_case(case, solution) for case in cases]
    report = aggregate(cases, results, args.label)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"label={args.label} score={report['score'] * 100:.2f}% "
        f"unit={report['unit_score']['score'] * 100:.2f}% "
        f"system={report['system_score']['score'] * 100:.2f}% "
        f"gap={report['gap_pp']:.2f}pp"
    )
    if report["failed_cases"]:
        print(f"FAILED {len(report['failed_cases'])} cases")
        for item in report["failed_cases"]:
            print(f"  {item['id']}: {item['errors']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

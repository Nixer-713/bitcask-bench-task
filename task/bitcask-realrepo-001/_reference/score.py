#!/usr/bin/env python3
"""Score a kvmini.py solution against rubric.json.

Usage:
    python3 score.py --solution PATH/TO/kvmini.py --rubric rubric.json \
        [--out score_report.json] [--label reference]

For each case the harness creates a fresh temp workspace, writes any
`setup_files`, then runs the case's commands in sequence (each command is a
separate process invocation, exactly like real usage). It enforces expect_error
semantics and applies the declared checks, producing an aggregate report in the
same schema family as the reference score reports.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile


def _norm_command(item):
    if isinstance(item, dict):
        return list(item["args"]), bool(item.get("expect_error", False))
    return list(item), False


def _check_stdout_equals(outputs, spec, errs):
    for idx, expected in spec.items():
        got = outputs[int(idx)].strip()
        if got != str(expected):
            errs.append(f"cmd{idx} stdout_equals: expected {expected!r}, got {got!r}")


def _check_stdout_contains(outputs, spec, errs):
    for idx, sub in spec.items():
        if sub not in outputs[int(idx)]:
            errs.append(f"cmd{idx} stdout_contains: {sub!r} not in output")


def _json_subset(expected, actual):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(k in actual and _json_subset(v, actual[k])
                   for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return all(any(_json_subset(e, a) for a in actual) for e in expected)
    return expected == actual


def _check_stdout_json(outputs, spec, errs, subset=False):
    for idx, expected in spec.items():
        raw = outputs[int(idx)].strip()
        try:
            actual = json.loads(raw)
        except json.JSONDecodeError:
            errs.append(f"cmd{idx} stdout_json: output is not valid JSON: {raw!r}")
            continue
        ok = _json_subset(expected, actual) if subset else (expected == actual)
        if not ok:
            errs.append(f"cmd{idx} stdout_json: expected {expected!r}, got {actual!r}")


def run_case(case, solution):
    errs = []
    with tempfile.TemporaryDirectory() as ws:
        for name, content in case.get("setup_files", {}).items():
            with open(os.path.join(ws, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        commands = [_norm_command(c) for c in case["commands"]]
        env = dict(os.environ)
        env.update({k: str(v) for k, v in case.get("env", {}).items()})

        outputs = []
        for i, (args, expect_error) in enumerate(commands):
            proc = subprocess.run(
                [sys.executable, solution, *args],
                cwd=ws, capture_output=True, text=True, env=env,
            )
            outputs.append(proc.stdout)
            if expect_error and proc.returncode == 0:
                errs.append(f"cmd{i} expected nonzero exit, got 0")
            if not expect_error and proc.returncode != 0:
                errs.append(
                    f"cmd{i} expected success, got exit {proc.returncode}: "
                    f"{proc.stderr.strip()!r}")

        checks = case.get("checks", {})
        if "stdout_equals" in checks:
            _check_stdout_equals(outputs, checks["stdout_equals"], errs)
        if "stdout_contains" in checks:
            _check_stdout_contains(outputs, checks["stdout_contains"], errs)
        if "stdout_json" in checks:
            _check_stdout_json(outputs, checks["stdout_json"], errs, subset=False)
        if "stdout_json_contains" in checks:
            _check_stdout_json(outputs, checks["stdout_json_contains"], errs,
                               subset=True)
    return errs


def aggregate(cases, results, label):
    def bucket():
        return {"weight": 0, "passed_weight": 0, "cases": 0, "passed_cases": 0}

    def with_score(b):
        out = dict(b)
        out["score"] = round(out["passed_weight"] / out["weight"], 4) if out["weight"] else 0.0
        return out

    def summary_buckets(store):
        return {
            key: {
                "weight": b["weight"],
                "passed_weight": b["passed_weight"],
                "cases": b["cases"],
                "passed": b["passed_cases"],
                "score": round(b["passed_weight"] / b["weight"], 4) if b["weight"] else 0.0,
            }
            for key, b in store.items()
        }

    layers, categories, dims = {}, {}, {}
    total_w = passed_w = 0
    failed = []
    all_cases = []
    for case, errs in zip(cases, results):
        passed = not errs
        w = case["weight"]
        total_w += w
        passed_w += w if passed else 0
        for store, key in ((layers, case["layer"]),
                           (categories, case.get("category", "uncategorized"))):
            b = store.setdefault(key, bucket())
            b["weight"] += w
            b["cases"] += 1
            if passed:
                b["passed_weight"] += w
                b["passed_cases"] += 1
        if case["layer"] == "system":
            b = dims.setdefault(case["system_dimension"], bucket())
            b["weight"] += w
            b["cases"] += 1
            if passed:
                b["passed_weight"] += w
                b["passed_cases"] += 1
        entry = {"id": case["id"], "layer": case["layer"],
                 "category": case.get("category"), "weight": w,
                 "passed": passed}
        if case["layer"] == "system":
            entry["system_dimension"] = case["system_dimension"]
        if not passed:
            entry["errors"] = errs
            failed.append(entry)
        all_cases.append(entry)

    unit = layers.get("unit", bucket())
    system = layers.get("system", bucket())
    unit_score = with_score(unit)
    system_score = with_score(system)

    return {
        "total_cases": len(cases),
        "passed_cases": sum(1 for _, e in zip(cases, results) if not e),
        "total_weight": total_w,
        "passed_weight": passed_w,
        "score": round(passed_w / total_w, 4) if total_w else 0.0,
        "unit_score": unit_score,
        "system_score": system_score,
        "unit_system_gap": round(unit_score["score"] - system_score["score"], 4),
        "layers": summary_buckets(layers),
        "categories": summary_buckets(categories),
        "system_dimensions": summary_buckets(dims),
        "failed_cases": failed,
        "all_cases": all_cases,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True)
    ap.add_argument("--rubric", required=True)
    ap.add_argument("--out")
    ap.add_argument("--label", default="solution")
    args = ap.parse_args()

    with open(args.rubric, encoding="utf-8") as fh:
        cases = json.load(fh)

    solution = os.path.abspath(args.solution)
    results = [run_case(c, solution) for c in cases]
    report = aggregate(cases, results, args.label)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    print(f"label={args.label}  score={report['score']*100:.2f}%  "
          f"unit={report['unit_score']['score']*100:.2f}%  "
          f"system={report['system_score']['score']*100:.2f}%  "
          f"gap={report['unit_system_gap']*100:.2f}pp")
    if report["failed_cases"]:
        print(f"FAILED {len(report['failed_cases'])} case(s):")
        for fc in report["failed_cases"]:
            print(f"  {fc['id']}: {fc['errors']}")
    return 0 if not report["failed_cases"] else 1


if __name__ == "__main__":
    sys.exit(main())

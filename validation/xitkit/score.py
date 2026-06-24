#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["cases"] if isinstance(data, dict) and "cases" in data else data


def write_setup(workdir: Path, setup: dict[str, str]) -> None:
    for name, content in setup.items():
        path = workdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def subset(expected, actual) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(k in actual and subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) < len(expected):
            return False
        return all(subset(e, actual[i]) for i, e in enumerate(expected))
    return expected == actual


def run_case(case: dict, script: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"{case['id']}_") as tmp:
        workdir = Path(tmp)
        write_setup(workdir, case.get("setup_files", {}))
        stdout_json: dict[str, object] = {}
        command_results = []
        for idx, command in enumerate(case["commands"]):
            expect_error = False
            if isinstance(command, dict):
                args = command["args"]
                expect_error = bool(command.get("expect_error"))
            else:
                args = command
            proc = subprocess.run(
                [sys.executable, str(script), *args],
                cwd=workdir,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
            command_results.append(
                {
                    "index": idx,
                    "args": args,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                }
            )
            if expect_error:
                if proc.returncode == 0:
                    return fail(case, f"command {idx} expected error but exited 0", command_results)
                continue
            if proc.returncode != 0:
                return fail(case, f"command {idx} exited {proc.returncode}: {proc.stderr.strip()}", command_results)
            try:
                stdout_json[str(idx)] = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                return fail(case, f"command {idx} stdout is not JSON: {exc}", command_results)

        checks = case.get("checks", {})
        for index, expected in checks.get("stdout_json", {}).items():
            if stdout_json.get(index) != expected:
                return fail(case, f"stdout_json[{index}] mismatch", command_results, stdout_json)
        for index, expected in checks.get("stdout_json_contains", {}).items():
            if index not in stdout_json or not subset(expected, stdout_json[index]):
                return fail(case, f"stdout_json_contains[{index}] mismatch", command_results, stdout_json)
        for index, expected_len in checks.get("stdout_json_length", {}).items():
            actual = stdout_json.get(index)
            if not hasattr(actual, "__len__") or len(actual) != expected_len:
                return fail(case, f"stdout_json_length[{index}] expected {expected_len}", command_results, stdout_json)
        for filename, snippets in checks.get("file_contains", {}).items():
            text = (workdir / filename).read_text(encoding="utf-8")
            for snippet in snippets:
                if snippet not in text:
                    return fail(case, f"{filename} missing snippet {snippet!r}", command_results, stdout_json)
        for filename, snippets in checks.get("file_not_contains", {}).items():
            text = (workdir / filename).read_text(encoding="utf-8")
            for snippet in snippets:
                if snippet in text:
                    return fail(case, f"{filename} unexpectedly contains {snippet!r}", command_results, stdout_json)
        return {
            "id": case["id"],
            "layer": case["layer"],
            "passed": True,
            "diagnostic": "",
            "commands": command_results,
        }


def fail(case, message, commands, stdout_json=None) -> dict:
    return {
        "id": case["id"],
        "layer": case["layer"],
        "passed": False,
        "diagnostic": message,
        "commands": commands,
        "stdout_json": stdout_json or {},
    }


def summarize(results: list[dict]) -> dict:
    unit = [r for r in results if r["layer"] == "unit"]
    system = [r for r in results if r["layer"] == "system"]
    unit_pass = sum(r["passed"] for r in unit)
    system_pass = sum(r["passed"] for r in system)
    unit_score = 100.0 * unit_pass / len(unit) if unit else 0.0
    system_score = 100.0 * system_pass / len(system) if system else 0.0
    return {
        "total_passed": sum(r["passed"] for r in results),
        "total_cases": len(results),
        "unit_passed": unit_pass,
        "unit_total": len(unit),
        "system_passed": system_pass,
        "system_total": len(system),
        "unit_score": round(unit_score, 2),
        "system_score": round(system_score, 2),
        "gap_pp": round(unit_score - system_score, 2),
        "failed_case_ids": [r["id"] for r in results if not r["passed"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rubric", default="task/xitkit-realrepo-001/rubric.json")
    parser.add_argument("--script", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    cases = load_cases(Path(args.rubric))
    script = Path(args.script).resolve()
    results = [run_case(case, script) for case in cases]
    report = {"summary": summarize(results), "results": results}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if report["summary"]["total_passed"] == report["summary"]["total_cases"] else 1)


if __name__ == "__main__":
    main()

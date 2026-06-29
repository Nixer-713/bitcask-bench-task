#!/usr/bin/env bash
set -uo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
SUBMISSION_DIR="${SUBMISSION_DIR:-/workspace/submission}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_DIR="${ORACLE_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)/oracle}"
REPORT_DIR="${REPORT_DIR:-/workspace/report}"
MANIFEST_PATH="${SCORING_MANIFEST:-$(cd "${SCRIPT_DIR}/.." && pwd)/scoring_manifest.json}"

mkdir -p "${REPORT_DIR}"
export PYTHONDONTWRITEBYTECODE=1

manifest_value() {
  local query="$1"
  local default_value="$2"
  "${PYTHON_BIN}" - "$MANIFEST_PATH" "$query" "$default_value" <<'PY'
import json
import sys

manifest_path, query, default_value = sys.argv[1:4]
with open(manifest_path, encoding="utf-8") as f:
    manifest = json.load(f)

if query.startswith("timeout:"):
    key = query.split(":", 1)[1]
    print(manifest.get("timeouts", {}).get(key, default_value))
elif query.startswith("path:"):
    stage_id = query.split(":", 1)[1]
    for group in manifest.get("test_groups", []):
        if group.get("id") == stage_id:
            print(group.get("path", default_value))
            break
    else:
        print(default_value)
elif query == "task_id":
    print(manifest.get("task_id", default_value))
else:
    print(default_value)
PY
}

TASK_ID="$(manifest_value task_id doit-realrepo-001)"
INSTALL_TIMEOUT="$(manifest_value timeout:install_seconds 300)"
CONTRACT_TIMEOUT="$(manifest_value timeout:contract_seconds 180)"
UNIT_TIMEOUT="$(manifest_value timeout:unit_seconds 300)"
INTEGRATION_TIMEOUT="$(manifest_value timeout:integration_seconds 600)"
CONTRACT_PATH="${ORACLE_DIR}/$(manifest_value path:contract contract_tests)"
UNIT_PATH="${ORACLE_DIR}/$(manifest_value path:unit filtered_unit_tests)"
INTEGRATION_PATH="${ORACLE_DIR}/$(manifest_value path:integration filtered_integration_tests)"

run_stage() {
  local stage="$1"
  local timeout_seconds="$2"
  shift 2
  local stdout_file="${REPORT_DIR}/${stage}.stdout.txt"
  local stderr_file="${REPORT_DIR}/${stage}.stderr.txt"
  "${PYTHON_BIN}" - "$timeout_seconds" "$stdout_file" "$stderr_file" "$@" <<'PY'
import subprocess
import sys

timeout_seconds = float(sys.argv[1])
stdout_file = sys.argv[2]
stderr_file = sys.argv[3]
cmd = sys.argv[4:]

with open(stdout_file, "w", encoding="utf-8") as out, open(stderr_file, "w", encoding="utf-8") as err:
    try:
        completed = subprocess.run(cmd, stdout=out, stderr=err, text=True, timeout=timeout_seconds)
        raise SystemExit(completed.returncode)
    except subprocess.TimeoutExpired:
        err.write(f"TIMEOUT after {timeout_seconds:g} seconds\n")
        raise SystemExit(124)
PY
  local rc=$?
  printf '%s' "${rc}" >"${REPORT_DIR}/${stage}.exitcode"
  return "${rc}"
}

parse_junit() {
  local xml_path="$1"
  local out_path="$2"
  "${PYTHON_BIN}" - "$xml_path" "$out_path" <<'PY'
import json
import sys
import xml.etree.ElementTree as ET

xml_path, out_path = sys.argv[1], sys.argv[2]
summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "passed": 0}
try:
    root = ET.parse(xml_path).getroot()
    if root.tag == "testsuite":
        suites = [root]
    else:
        suites = list(root.iter("testsuite"))
    for suite in suites:
        summary["tests"] += int(suite.attrib.get("tests", 0))
        summary["failures"] += int(suite.attrib.get("failures", 0))
        summary["errors"] += int(suite.attrib.get("errors", 0))
        summary["skipped"] += int(suite.attrib.get("skipped", 0))
    summary["passed"] = summary["tests"] - summary["failures"] - summary["errors"] - summary["skipped"]
except Exception as exc:
    summary["parse_error"] = str(exc)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, sort_keys=True)
PY
}

write_skipped_stage() {
  local stage="$1"
  printf 'skipped because install failed\n' >"${REPORT_DIR}/${stage}.stdout.txt"
  : >"${REPORT_DIR}/${stage}.stderr.txt"
  printf '99' >"${REPORT_DIR}/${stage}.exitcode"
  "${PYTHON_BIN}" - "$REPORT_DIR/${stage}.junit_summary.json" <<'PY'
import json
import sys
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "passed": 0, "skipped_stage": True}, f, indent=2, sort_keys=True)
PY
}

run_stage install "${INSTALL_TIMEOUT}" "${PYTHON_BIN}" -m pip install -e "${SUBMISSION_DIR}"
INSTALL_RC=$?

if [ "${INSTALL_RC}" -eq 0 ]; then
  run_stage contract "${CONTRACT_TIMEOUT}" "${PYTHON_BIN}" -m pytest "${CONTRACT_PATH}" -q -p no:cacheprovider --junitxml="${REPORT_DIR}/contract.junit.xml"
  CONTRACT_RC=$?
  parse_junit "${REPORT_DIR}/contract.junit.xml" "${REPORT_DIR}/contract.junit_summary.json"

  run_stage unit "${UNIT_TIMEOUT}" "${PYTHON_BIN}" -m pytest "${UNIT_PATH}" -q -p no:cacheprovider --junitxml="${REPORT_DIR}/unit.junit.xml"
  UNIT_RC=$?
  parse_junit "${REPORT_DIR}/unit.junit.xml" "${REPORT_DIR}/unit.junit_summary.json"

  run_stage integration "${INTEGRATION_TIMEOUT}" "${PYTHON_BIN}" -m pytest "${INTEGRATION_PATH}" -q -p no:cacheprovider --junitxml="${REPORT_DIR}/integration.junit.xml"
  INTEGRATION_RC=$?
  parse_junit "${REPORT_DIR}/integration.junit.xml" "${REPORT_DIR}/integration.junit_summary.json"
else
  CONTRACT_RC=99
  UNIT_RC=99
  INTEGRATION_RC=99
  write_skipped_stage contract
  write_skipped_stage unit
  write_skipped_stage integration
fi

"${PYTHON_BIN}" - "$REPORT_DIR" "$TASK_ID" "$MANIFEST_PATH" "$INSTALL_RC" "$CONTRACT_RC" "$UNIT_RC" "$INTEGRATION_RC" <<'PY'
import json
import pathlib
import sys

report_dir = pathlib.Path(sys.argv[1])
task_id = sys.argv[2]
manifest_path = sys.argv[3]
codes = {
    "install": int(sys.argv[4]),
    "contract": int(sys.argv[5]),
    "unit": int(sys.argv[6]),
    "integration": int(sys.argv[7]),
}

def load_stage(name):
    summary_path = report_dir / f"{name}.junit_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "passed": 0}
    summary.update({
        "exit_code": codes[name],
        "stdout": str(report_dir / f"{name}.stdout.txt"),
        "stderr": str(report_dir / f"{name}.stderr.txt"),
        "junit": str(report_dir / f"{name}.junit.xml") if (report_dir / f"{name}.junit.xml").exists() else "",
    })
    return summary

contract = load_stage("contract")
unit = load_stage("unit")
integration = load_stage("integration")

def rate(stage):
    return (stage["passed"] / stage["tests"]) if stage.get("tests") else 0.0

unit_rate = rate(unit)
integration_rate = rate(integration)
all_tests = contract["tests"] + unit["tests"] + integration["tests"]
all_passed = contract["passed"] + unit["passed"] + integration["passed"]
overall = (all_passed / all_tests) if all_tests else 0.0

summary = {
    "task_id": task_id,
    "scoring_manifest": manifest_path,
    "install": {
        "passed": codes["install"] == 0,
        "exit_code": codes["install"],
        "stdout": str(report_dir / "install.stdout.txt"),
        "stderr": str(report_dir / "install.stderr.txt"),
    },
    "stages": {
        "contract": contract,
        "unit": unit,
        "integration": integration,
    },
    "summary": {
        "contract_passed": contract["passed"],
        "contract_total": contract["tests"],
        "unit_passed": unit["passed"],
        "unit_total": unit["tests"],
        "integration_passed": integration["passed"],
        "integration_total": integration["tests"],
        "unit_pass_rate": unit_rate,
        "integration_pass_rate": integration_rate,
        "integration_gap_pp": 100.0 * (unit_rate - integration_rate),
        "overall_pass_rate": overall,
    },
}
(report_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
PY

if [ "${INSTALL_RC}" -eq 0 ] && [ "${CONTRACT_RC}" -eq 0 ] && [ "${UNIT_RC}" -eq 0 ] && [ "${INTEGRATION_RC}" -eq 0 ]; then
  exit 0
fi
exit 1

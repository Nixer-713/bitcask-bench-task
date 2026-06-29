import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


def write_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return path


def write_dodo(workspace: Path, text: str, name: str = "dodo.py") -> Path:
    return write_file(workspace / name, text)


def run_minidoit(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    return subprocess.run(
        [sys.executable, "-m", "minidoit", *map(str, args)],
        cwd=workspace,
        text=True,
        capture_output=True,
        env=env,
    )


def run_console(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    return subprocess.run(
        ["minidoit", *map(str, args)],
        cwd=workspace,
        text=True,
        capture_output=True,
        env=env,
    )


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def stdout_json(result: subprocess.CompletedProcess[str]):
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def assert_failed_without_state_or_targets(
    result: subprocess.CompletedProcess[str],
    workspace: Path,
    *paths: str,
) -> None:
    assert result.returncode != 0
    assert result.stderr.strip()
    assert not (workspace / ".minidoit.db.json").exists()
    for rel in paths:
        assert not (workspace / rel).exists()


def console_available() -> bool:
    return shutil.which("minidoit") is not None

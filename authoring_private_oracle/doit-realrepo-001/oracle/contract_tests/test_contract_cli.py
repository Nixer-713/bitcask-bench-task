import importlib

from conftest import console_available, run_console, run_minidoit


def test_public_package_import_and_version():
    pkg = importlib.import_module("minidoit")
    assert isinstance(pkg.__version__, str)
    assert pkg.__version__


def test_module_execution_help(tmp_path):
    result = run_minidoit(tmp_path, "--help")
    assert result.returncode == 0
    assert "run" in result.stdout
    assert "list" in result.stdout
    assert "dumpdb" in result.stdout


def test_console_script_version(tmp_path):
    assert console_available(), "console script 'minidoit' is not on PATH"
    result = run_console(tmp_path, "--version")
    assert result.returncode == 0
    assert result.stdout.strip()


def test_dumpdb_rejects_file_option(tmp_path):
    result = run_minidoit(tmp_path, "dumpdb", "--file", "missing.py", "--json")
    assert result.returncode != 0
    assert result.stderr.strip()

from conftest import assert_failed_without_state_or_targets, run_minidoit, stdout_json, write_dodo, write_file


def test_list_json_reports_static_literal_task(tmp_path):
    write_file(tmp_path / "src.txt", "input")
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {
                'actions': ['write out.txt hello'],
                'file_dep': ['src.txt'],
                'targets': ['out.txt'],
                'task_dep': [],
                'doc': 'Build output',
                'verbosity': 2,
            }
        """,
    )

    data = stdout_json(run_minidoit(tmp_path, "list", "--json", "--status"))

    assert data["tasks"] == [
        {
            "name": "build",
            "doc": "Build output",
            "file_dep": ["src.txt"],
            "targets": ["out.txt"],
            "task_dep": [],
            "status": "run",
        }
    ]


def test_info_json_reports_reasons_before_run(tmp_path):
    write_file(tmp_path / "src.txt", "input")
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt hello'], 'file_dep': ['src.txt'], 'targets': ['out.txt'], 'clean': True}
        """,
    )

    data = stdout_json(run_minidoit(tmp_path, "info", "build", "--json"))

    assert data["name"] == "build"
    assert data["status"] == "run"
    assert "no_success_state" in data["reasons"]
    assert data["clean"] is True


def test_duplicate_task_names_are_rejected_before_writes(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write one.txt one']}

        def task_build():
            return {'actions': ['write two.txt two']}
        """,
    )

    result = run_minidoit(tmp_path, "run")

    assert_failed_without_state_or_targets(result, tmp_path, "one.txt", "two.txt")


def test_unsupported_task_field_is_rejected(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_bad():
            return {'actions': ['write out.txt ok'], 'params': []}
        """,
    )

    result = run_minidoit(tmp_path, "list", "--json")

    assert result.returncode != 0
    assert result.stderr.strip()


def test_invalid_relative_paths_are_rejected_before_writes(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_bad():
            return {'actions': ['write ../escape.txt no'], 'targets': ['../escape.txt']}
        """,
    )

    result = run_minidoit(tmp_path, "run")

    assert_failed_without_state_or_targets(result, tmp_path, "escape.txt")


def test_safe_actions_write_append_copy_delete(tmp_path):
    write_file(tmp_path / "src.txt", "copied")
    write_dodo(
        tmp_path,
        """
        def task_actions():
            return {'actions': [
                'write out.txt hello',
                'append out.txt -again',
                'copy src.txt copied.txt',
                'delete gone.txt',
            ], 'targets': ['out.txt', 'copied.txt']}
        """,
    )

    result = run_minidoit(tmp_path, "run", "actions")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "hello-again"
    assert (tmp_path / "copied.txt").read_text(encoding="utf-8") == "copied"


def test_dumpdb_json_empty_without_task_file(tmp_path):
    data = stdout_json(run_minidoit(tmp_path, "dumpdb", "--json"))

    assert data == {"version": 1, "tasks": {}}


def test_config_selects_task_file_and_db_file(tmp_path):
    write_file(
        tmp_path / "pyproject.toml",
        """
        [tool.minidoit]
        task_file = "tasks/alt.py"
        db_file = "state/db.json"
        """,
    )
    write_dodo(
        tmp_path / "tasks",
        """
        def task_cfg():
            return {'actions': ['write out.txt cfg'], 'targets': ['out.txt']}
        """,
        name="alt.py",
    )

    result = run_minidoit(tmp_path, "run")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "cfg"
    assert (tmp_path / "state" / "db.json").exists()


def test_cli_file_and_db_file_override_config(tmp_path):
    write_file(
        tmp_path / "pyproject.toml",
        """
        [tool.minidoit]
        task_file = "wrong.py"
        db_file = "wrong.json"
        """,
    )
    write_dodo(
        tmp_path,
        """
        def task_ok():
            return {'actions': ['write ok.txt yes'], 'targets': ['ok.txt']}
        """,
        name="chosen.py",
    )

    result = run_minidoit(tmp_path, "--file", "chosen.py", "--db-file", "state/chosen.json", "run")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "ok.txt").read_text(encoding="utf-8") == "yes"
    assert (tmp_path / "state" / "chosen.json").exists()
    assert not (tmp_path / "wrong.json").exists()


def test_malformed_toml_is_pre_execution_error(tmp_path):
    write_file(tmp_path / "pyproject.toml", "[tool.minidoit\n")
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt bad']}
        """,
    )

    result = run_minidoit(tmp_path, "run")

    assert_failed_without_state_or_targets(result, tmp_path, "out.txt")

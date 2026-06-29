from conftest import read_json, run_minidoit, stdout_json, write_dodo, write_file


def test_successful_run_writes_public_state_shape(tmp_path):
    write_file(tmp_path / "src.txt", "one")
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt one'], 'file_dep': ['src.txt'], 'targets': ['out.txt']}
        """,
    )

    result = run_minidoit(tmp_path, "run", "build")

    assert result.returncode == 0, result.stderr
    state = read_json(tmp_path / ".minidoit.db.json")
    task_state = state["tasks"]["build"]
    assert state["version"] == 1
    assert task_state["status"] == "success"
    assert task_state["last_result"] == "success"
    assert list(task_state["file_dep"]) == ["src.txt"]
    assert task_state["targets"] == ["out.txt"]


def test_missing_file_dependency_is_task_error(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt impossible'], 'file_dep': ['missing.txt'], 'targets': ['out.txt']}
        """,
    )

    result = run_minidoit(tmp_path, "run", "build")

    assert result.returncode != 0
    assert result.stderr.strip()
    assert not (tmp_path / "out.txt").exists()


def test_info_reports_changed_file_dependency(tmp_path):
    write_file(tmp_path / "src.txt", "one")
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt built'], 'file_dep': ['src.txt'], 'targets': ['out.txt']}
        """,
    )
    assert run_minidoit(tmp_path, "run", "build").returncode == 0
    write_file(tmp_path / "src.txt", "two")

    data = stdout_json(run_minidoit(tmp_path, "info", "build", "--json"))

    assert data["status"] == "run"
    assert "changed_file_dep" in data["reasons"]


def test_uptodate_false_forces_rerun_status(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_always():
            return {'actions': ['write out.txt value'], 'targets': ['out.txt'], 'uptodate': False}
        """,
    )
    assert run_minidoit(tmp_path, "run", "always").returncode == 0

    data = stdout_json(run_minidoit(tmp_path, "info", "always", "--json"))

    assert data["status"] == "run"
    assert "uptodate_false" in data["reasons"]


def test_corrupted_state_is_pre_execution_error(tmp_path):
    write_file(tmp_path / ".minidoit.db.json", "{broken")
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt no'], 'targets': ['out.txt']}
        """,
    )

    result = run_minidoit(tmp_path, "run")

    assert result.returncode != 0
    assert not (tmp_path / "out.txt").exists()

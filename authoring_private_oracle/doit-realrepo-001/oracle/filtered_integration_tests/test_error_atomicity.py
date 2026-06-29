from conftest import read_json, run_minidoit, stdout_json, write_dodo, write_file


def test_pre_execution_parse_error_leaves_existing_state_and_targets(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt good'], 'targets': ['out.txt']}
        """,
    )
    assert run_minidoit(tmp_path, "run", "build").returncode == 0
    before_state = read_json(tmp_path / ".minidoit.db.json")
    before_target = (tmp_path / "out.txt").read_text(encoding="utf-8")
    write_dodo(
        tmp_path,
        """
        import os

        def task_build():
            return {'actions': ['write out.txt bad'], 'targets': ['out.txt']}
        """,
    )

    result = run_minidoit(tmp_path, "run", "build")

    assert result.returncode != 0
    assert read_json(tmp_path / ".minidoit.db.json") == before_state
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == before_target


def test_operation_order_clean_then_run_then_forget(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt value'], 'targets': ['out.txt'], 'clean': True}
        """,
    )
    assert run_minidoit(tmp_path, "run", "build").returncode == 0
    assert run_minidoit(tmp_path, "clean", "build").returncode == 0
    info_after_clean = stdout_json(run_minidoit(tmp_path, "info", "build", "--json"))
    rerun = run_minidoit(tmp_path, "run", "build")
    assert rerun.returncode == 0, rerun.stderr
    assert run_minidoit(tmp_path, "forget", "--all").returncode == 0
    dump = stdout_json(run_minidoit(tmp_path, "dumpdb", "--json"))

    assert info_after_clean["status"] == "run"
    assert "missing_target" in info_after_clean["reasons"]
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "value"
    assert dump["tasks"] == {}

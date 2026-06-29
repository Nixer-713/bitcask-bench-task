from conftest import read_json, run_minidoit, stdout_json, write_dodo, write_file


def test_run_then_reports_and_dumpdb_agree(tmp_path):
    write_file(tmp_path / "src.txt", "alpha")
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt alpha'], 'file_dep': ['src.txt'], 'targets': ['out.txt'], 'doc': 'Build alpha'}
        """,
    )

    first = run_minidoit(tmp_path, "run")
    second = run_minidoit(tmp_path, "run")
    listing = stdout_json(run_minidoit(tmp_path, "list", "--json", "--status"))
    info = stdout_json(run_minidoit(tmp_path, "info", "build", "--json"))
    dump = stdout_json(run_minidoit(tmp_path, "dumpdb", "--json"))

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "execut" in first.stdout.lower()
    assert "skip" in second.stdout.lower()
    assert listing["tasks"][0]["status"] == "up_to_date"
    assert info["status"] == "up_to_date"
    assert dump == read_json(tmp_path / ".minidoit.db.json")
    assert dump["tasks"]["build"]["status"] == "success"


def test_dependency_order_and_cross_task_state(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_prepare():
            return {'actions': ['write build/src.txt prepared'], 'targets': ['build/src.txt']}

        def task_package():
            return {'actions': ['copy build/src.txt dist/pkg.txt'], 'task_dep': ['prepare'], 'file_dep': ['build/src.txt'], 'targets': ['dist/pkg.txt']}
        """,
    )

    result = run_minidoit(tmp_path, "run", "package")
    data = stdout_json(run_minidoit(tmp_path, "dumpdb", "--json"))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "dist" / "pkg.txt").read_text(encoding="utf-8") == "prepared"
    assert set(data["tasks"]) == {"prepare", "package"}


def test_clean_forget_target_and_state_consistency(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt built'], 'targets': ['out.txt'], 'clean': True}
        """,
    )
    assert run_minidoit(tmp_path, "run", "build").returncode == 0

    clean = run_minidoit(tmp_path, "clean", "build", "--forget")
    info = stdout_json(run_minidoit(tmp_path, "info", "build", "--json"))
    dump = stdout_json(run_minidoit(tmp_path, "dumpdb", "--json"))

    assert clean.returncode == 0, clean.stderr
    assert not (tmp_path / "out.txt").exists()
    assert info["status"] == "run"
    assert "no_success_state" in info["reasons"]
    assert dump["tasks"] == {}


def test_forget_keeps_target_but_forces_future_run(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_build():
            return {'actions': ['write out.txt rebuilt'], 'targets': ['out.txt']}
        """,
    )
    assert run_minidoit(tmp_path, "run", "build").returncode == 0
    assert run_minidoit(tmp_path, "forget", "build").returncode == 0

    info = stdout_json(run_minidoit(tmp_path, "info", "build", "--json"))

    assert (tmp_path / "out.txt").exists()
    assert info["status"] == "run"
    assert "no_success_state" in info["reasons"]


def test_failed_dependency_blocks_dependent_and_no_false_success(tmp_path):
    write_dodo(
        tmp_path,
        """
        def task_prepare():
            return {'actions': ['write before.txt ok', 'fail boom', 'write after.txt no'], 'targets': ['before.txt', 'after.txt']}

        def task_package():
            return {'actions': ['write package.txt no'], 'task_dep': ['prepare'], 'targets': ['package.txt']}
        """,
    )

    result = run_minidoit(tmp_path, "run", "package")
    dump = stdout_json(run_minidoit(tmp_path, "dumpdb", "--json"))

    assert result.returncode != 0
    assert not (tmp_path / "after.txt").exists()
    assert not (tmp_path / "package.txt").exists()
    assert "prepare" not in dump["tasks"]
    assert "package" not in dump["tasks"]


def test_config_boundary_with_custom_task_and_state_paths(tmp_path):
    write_file(
        tmp_path / "pyproject.toml",
        """
        [tool.minidoit]
        task_file = "tasks/build.py"
        db_file = "state/minidoit.json"
        """,
    )
    write_dodo(
        tmp_path / "tasks",
        """
        def task_build():
            return {'actions': ['write generated/out.txt cfg'], 'targets': ['generated/out.txt']}
        """,
        name="build.py",
    )

    run = run_minidoit(tmp_path, "run")
    dump = stdout_json(run_minidoit(tmp_path, "--db-file", "state/minidoit.json", "dumpdb", "--json"))

    assert run.returncode == 0, run.stderr
    assert (tmp_path / "generated" / "out.txt").read_text(encoding="utf-8") == "cfg"
    assert "build" in dump["tasks"]

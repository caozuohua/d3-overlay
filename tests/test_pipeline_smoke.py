"""Smoke test for BuildAssistant data pipeline script."""

import json
import os
import subprocess
import sys
import tempfile


def test_build_data_pipeline_runs_without_error(tmp_path):
    script_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scripts", "build_data_pipeline.py")
    )

    src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    tmpdir = str(tmp_path)
    output_path = os.path.join(tmpdir, "data", "d3-data.json")

    env = os.environ.copy()
    env["PYTHONPATH"] = src_root

    # Windows 下 subprocess 有时会触发 WinError 50；优先直接 import 运行，
    # 失败再回退到子进程，保证 pipeline smoke 不脆。
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_data_pipeline", script_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        old_cwd = os.getcwd()
        old_argv = sys.argv[:]
        try:
            os.chdir(tmpdir)
            sys.argv[:] = [script_path]
            spec.loader.exec_module(mod)
            mod.main()
        finally:
            sys.argv[:] = old_argv
            os.chdir(old_cwd)
    except Exception:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=tmpdir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"pipeline exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    assert os.path.exists(output_path), f"missing output: {output_path}"

    with open(output_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    assert "skills" in data
    assert data["meta"]["classes_count"] >= 1
    assert data["skills"].get("barbarian")


if __name__ == "__main__":
    test_build_data_pipeline_runs_without_error()
    print("PASS  test_build_data_pipeline_runs_without_error")

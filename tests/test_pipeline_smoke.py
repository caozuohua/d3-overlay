"""Smoke test for BuildAssistant data pipeline script."""

import json
import os
import subprocess
import sys
import tempfile


def test_build_data_pipeline_runs_without_error():
    script_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scripts", "build_data_pipeline.py")
    )

    cwd = os.getcwd()
    tmpdir = tempfile.mkdtemp(prefix="d3oa-pipeline-")
    os.chdir(tmpdir)
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.abspath(os.path.join(tmpdir, "..", "..", "src"))

        result = subprocess.run(
            [sys.executable, script_path],
            cwd=tmpdir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"pipeline exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        output_path = os.path.abspath(
            os.path.join(tmpdir, "data", "d3-data.json")
        )
        assert os.path.exists(output_path), f"missing output: {output_path}"

        with open(output_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert "skills" in data
        assert "barbarian" in data["skills"]
        assert "Bash" in data["skills"]["barbarian"]
    finally:
        os.chdir(cwd)


if __name__ == "__main__":
    test_build_data_pipeline_runs_without_error()
    print("PASS  test_build_data_pipeline_runs_without_error")

"""Phase 3 Task 9 — BuildAssistant 数据管道冒烟测试。

运行:
    python tests/test_pipeline_smoke.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_build_data_pipeline_runs_without_error():
    script = _repo_root() / "scripts" / "build_data_pipeline.py"
    assert script.is_file(), f"pipeline script not found: {script}"

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(_repo_root()),
        env={**os.environ},
    )
    assert result.returncode == 0, (
        f"Exit code {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert "解析到的职业数量" in combined or "class" in combined, "缺少 class summary 输出"
    assert "barbarian" in combined, "缺少示例职业输出"


if __name__ == "__main__":
    failed = 0
    for name, test in sorted(globals().items()):
        if not name.startswith("test_") or not callable(test):
            continue
        try:
            test()
            print(f"  PASS  {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    total = sum(1 for k in globals() if k.startswith("test_") and callable(globals()[k]))
    print(f"\n{total - failed}/{total} passed")
    sys.exit(1 if failed else 0)

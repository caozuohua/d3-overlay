"""
Config.reload() 与基础 watch 监听测试
运行:
    python tests/test_config_reload.py          # 直接跑
    python -m pytest tests/test_config_reload.py -q
"""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config import Config


def test_config_edit_reload_reflects_disk_change():
    """外部修改配置文件后，reload() 应反映磁盘最新值。"""
    tmp_dir = tempfile.mkdtemp(prefix="d3oa_reload_")
    path = os.path.join(tmp_dir, "config.json")

    # 写入初始配置
    initial = {"overlay": {"opacity": 0.85, "position": "top-right"}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    cfg = Config(config_path=path)
    cfg.load()
    assert cfg.get("overlay.opacity") == 0.85
    assert cfg.get("overlay.position") == "top-right"

    # 外部篡改磁盘上的配置文件
    mutated = {"overlay": {"opacity": 0.42, "position": "bottom-left"}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mutated, f)

    # 让 mtime 足够不同
    time.sleep(0.05)

    cfg.reload()
    assert cfg.get("overlay.opacity") == 0.42, f"reload 后 opacity 应为 0.42，实际: {cfg.get('overlay.opacity')}"
    assert cfg.get("overlay.position") == "bottom-left", f"reload 后 position 应为 bottom-left，实际: {cfg.get('overlay.position')}"

    # 清理
    for p in [path, path + ".bak", path + ".tmp"]:
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass


def test_config_reload_without_path_does_not_raise():
    """无显式路径时 instantiate Config() 并调用 reload()，不应抛异常。"""
    cfg = Config()
    # 使用临时路径，避免污染默认 ~/.d3oa
    tmp_dir = tempfile.mkdtemp(prefix="d3oa_reload_nopath_")
    path = os.path.join(tmp_dir, "config.json")
    cfg._config_path = path
    # 第一次 load 创建默认文件
    cfg.load()

    # reload 应静默成功
    cfg.reload()
    assert cfg.get("overlay.opacity") == 0.85

    # 清理
    for p in [path, path + ".bak", path + ".tmp"]:
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

"""
F3 (TDD): Blizzard API 技能数据

RED: get_hero_skills 应命中 /d3/data/hero/{class_slug} 并返回 JSON。

用 unittest.mock 替换 Session，验证 endpoint 构造及无 token 行为。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest import mock


def test_get_hero_skills_missing_token_returns_none():
    """无 token / client 时，get_hero_skills 应返回 None。"""
    from data_provider import D3APIClient

    with mock.patch("requests.Session"):
        client = D3APIClient(region="us")
        result = client.get_hero_skills("barbarian")
        assert result is None, f"期望 None，实际为 {result!r}"


def test_get_hero_skills_endpoint_formed():
    """断言 endpoint 是 /d3/data/hero/barbarian。"""
    from data_provider import D3APIClient

    class FakeResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {"ok": True}

    got = {}

    def fake_get(url, **kw):
        got["url"] = url
        return FakeResp()

    with mock.patch("requests.Session") as Sess:
        sess = Sess.return_value
        sess.get.side_effect = fake_get
        client = D3APIClient(region="us", access_token="FAKE")
        result = client.get_hero_skills("barbarian")
        assert result == {"ok": True}
        assert got["url"].endswith("/d3/data/hero/barbarian"), \
            f"endpoint 错误：{got['url']}"


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
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

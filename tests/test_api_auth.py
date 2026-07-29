"""
F3 (TDD): Blizzard API 认证
RED: D3APIClient 应能通过 client-credentials 流程获取 access_token
（当前代码只从 config 读 token，从不获取；Blizzard D3 API 强制需 token）。

用 unittest.mock 替换 Session，验证：
  - 向 https://{region}.battle.net/oauth/token 发 POST (grant_type=client_credentials)
  - 解析返回的 access_token 并缓存
  - 后续 API 请求带 access_token 查询参数
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest import mock


def test_api_fetches_token_via_client_credentials():
    """修复后：无 token 时自动用 client-credentials 换取，并用于后续请求。"""
    from data_provider import D3APIClient

    fake_token = "FAKE_TOKEN_abc123"

    class FakeResp:
        def __init__(self, payload):
            self._p = payload
        def raise_for_status(self):
            pass
        def json(self):
            return self._p

    posted = {}

    def fake_post(url, **kw):
        posted["url"] = url
        posted["data"] = kw.get("data")
        posted["auth"] = kw.get("auth")
        return FakeResp({"access_token": fake_token, "token_type": "bearer"})

    def fake_get(url, **kw):
        # 验证请求带了 access_token
        assert kw.get("params", {}).get("access_token") == fake_token, "API 请求未带 access_token"
        return FakeResp({"ok": True})

    with mock.patch("requests.Session") as Sess:
        sess = Sess.return_value
        sess.post.side_effect = fake_post
        sess.get.side_effect = fake_get
        client = D3APIClient(region="us", access_token=None,
                             client_id="TEST_CLIENT", client_secret="TEST_SECRET")
        # 触发 token 获取
        client._ensure_token()
        assert client.access_token == fake_token, "未保存获取到的 token"
        assert "oauth/token" in posted["url"], f"未请求 oauth/token，url={posted['url']}"
        assert posted["data"] == {"grant_type": "client_credentials"}, "grant_type 错误"

        # 后续请求应使用 token
        res = client._request("/d3/profile/Foo-1234/")
        assert res == {"ok": True}


def test_api_uses_config_token_when_present():
    """已有 config token 时不应再去换（向后兼容手动填 token）。"""
    from data_provider import D3APIClient

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"ok": True}

    with mock.patch("requests.Session") as Sess:
        sess = Sess.return_value
        sess.post.side_effect = AssertionError("不应请求 oauth/token")
        sess.get.return_value = FakeResp()
        client = D3APIClient(region="us", access_token="MANUAL_TOKEN")
        res = client._request("/d3/profile/Foo-1234/")
        assert res == {"ok": True}
        # 确认 get 带的是手动 token
        _, kw = sess.get.call_args
        assert kw["params"]["access_token"] == "MANUAL_TOKEN"


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

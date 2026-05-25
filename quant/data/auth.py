#!/usr/bin/env python3
"""短线侠 duanxianxia.cn 登录认证模块。

用法:
  from data.auth import DuanxianxiaAuth
  auth = DuanxianxiaAuth()
  auth.login("18507507885", "qq781898")
  # 之后用 auth.opener 或 auth.session 发请求
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from pathlib import Path

BASE = "https://duanxianxia.cn"
SESSION_FILE = Path(__file__).parent / ".dx_session.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE,
    "Referer": f"{BASE}/",
    "X-Requested-With": "XMLHttpRequest",
}

RETRY_MAX = 3       # 最大重试次数
RETRY_BASE = 2.0    # 退避基数（秒），指数退避: base * 2^attempt


class DuanxianxiaAuth:
    """短线侠登录会话管理。"""

    def __init__(self):
        self.cj = http.cookiejar.LWPCookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj)
        )
        self.logged_in = False
        self.token = None
        self.cdkey = None
        self.username = None

    def login(self, username, password):
        """登录短线侠。返回 True/False。"""
        self.username = username

        # 先访问首页获取初始 cookie
        try:
            req = urllib.request.Request(BASE + "/", headers=HEADERS)
            self.opener.open(req, timeout=15)
        except Exception:
            pass

        # 登录
        data = urllib.parse.urlencode({
            "username": username,
            "password": password,
        }).encode()
        req = urllib.request.Request(
            BASE + "/api/userLogin",
            data=data,
            headers=HEADERS,
            method="POST",
        )
        resp = self.opener.open(req, timeout=15)
        result = json.loads(resp.read())

        if result.get("result") == "success":
            self.logged_in = True
            for c in self.cj:
                if c.name == "token":
                    self.token = c.value
                if c.name == "cdkey":
                    self.cdkey = c.value
            self._save_session()
            return True
        return False

    def _request_with_retry(self, path, data=None, method="POST", retries=RETRY_MAX):
        """带重试的 HTTP 请求。自动处理超时/5xx/JSON 错误，session 过期时重登录。"""
        last_error = None
        for attempt in range(retries + 1):
            try:
                body = urllib.parse.urlencode(data or {}).encode() if data is not None else None
                req = urllib.request.Request(
                    BASE + path, data=body, headers=HEADERS,
                    method="GET" if body is None else method,
                )
                resp = self.opener.open(req, timeout=20)
                raw = resp.read()

                # 检查是否被重定向到登录页
                if resp.getcode() == 200 and raw and raw[:20].strip().startswith(b"<!DOCTYPE"):
                    raise urllib.error.HTTPError(
                        BASE + path, 403, "Redirected to login page", resp.headers, None
                    )

                return json.loads(raw)

            except urllib.error.HTTPError as e:
                last_error = e
                if e.code in (401, 403):
                    if self.username and attempt < retries:
                        try:
                            self.login(self.username, "qq781898")
                            continue
                        except Exception:
                            pass
                if attempt < retries:
                    wait = RETRY_BASE * (2 ** attempt)
                    time.sleep(wait)
                else:
                    raise RuntimeError(
                        f"HTTP {e.code} on {path} after {retries} retries"
                    ) from e

            except urllib.error.URLError as e:
                last_error = e
                if attempt < retries:
                    wait = RETRY_BASE * (2 ** attempt)
                    time.sleep(wait)
                else:
                    raise RuntimeError(
                        f"Network error on {path} after {retries} retries: {e.reason}"
                    ) from e

            except json.JSONDecodeError as e:
                last_error = e
                if attempt < retries:
                    wait = RETRY_BASE * (2 ** attempt)
                    time.sleep(wait)
                else:
                    raise RuntimeError(
                        f"Invalid JSON on {path} after {retries} retries"
                    ) from e

        raise RuntimeError(f"Request failed on {path}: {last_error}")

    def get(self, path):
        """GET 请求（带认证 cookie + 重试）。"""
        return self._request_with_retry(path, data=None, method="GET")

    def post(self, path, data=None):
        """POST 请求（带认证 cookie + 重试）。"""
        return self._request_with_retry(path, data=data, method="POST")

    @property
    def cookie_string(self):
        """返回可在 requests 中使用的 cookie 字符串。"""
        return "; ".join(f"{c.name}={c.value}" for c in self.cj)

    def _save_session(self):
        """保存 session 到本地文件。"""
        data = {
            "username": self.username,
            "token": self.token,
            "cdkey": self.cdkey,
            "cookies": [
                {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
                for c in self.cj
            ],
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def from_saved(cls):
        """从本地文件恢复 session。"""
        if not SESSION_FILE.exists():
            return None
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        auth = cls()
        auth.username = data.get("username")
        auth.token = data.get("token")
        auth.cdkey = data.get("cdkey")

        # 恢复 cookies
        for c_data in data.get("cookies", []):
            cookie = http.cookiejar.Cookie(
                version=0,
                name=c_data["name"],
                value=c_data["value"],
                port=None,
                port_specified=False,
                domain=c_data["domain"],
                domain_specified=True,
                domain_initial_dot=False,
                path=c_data["path"],
                path_specified=True,
                secure=False,
                expires=None,
                discard=False,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
            auth.cj.set_cookie(cookie)

        auth.logged_in = bool(auth.token)
        return auth


if __name__ == "__main__":
    import sys
    user = sys.argv[1] if len(sys.argv) > 1 else "18507507885"
    pwd = sys.argv[2] if len(sys.argv) > 2 else "qq781898"

    auth = DuanxianxiaAuth()
    if auth.login(user, pwd):
        print(f"✓ 登录成功")
        print(f"  Token: {auth.token}")
        print(f"  CDKey: {auth.cdkey}")
        print(f"  Session 已保存到 {SESSION_FILE}")

        # 测试获取用户信息
        try:
            info = auth.get("/api/getUserInfo")
            print(f"  User: {info}")
        except Exception as e:
            print(f"  UserInfo: {e}")
    else:
        print("✗ 登录失败")

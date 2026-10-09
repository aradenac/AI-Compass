#!/usr/bin/env python3
"""Local CI-only end-to-end login/permission test through Caddy.

Provide AI_COMPASS_TEST_PASSWORD via environment, never via command args.
Requires an existing maintainer created by the bootstrap command.
"""
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

if len(sys.argv) != 2 or not os.environ.get("AI_COMPASS_TEST_PASSWORD"):
    raise SystemExit("Usage: AI_COMPASS_TEST_PASSWORD=... python3 scripts/smoke-auth.py USERNAME")

password = os.environ["AI_COMPASS_TEST_PASSWORD"]
port = os.environ.get("AI_COMPASS_HTTP_PORT", "8080")
base = f"http://127.0.0.1:{port}/api/v1/auth/"
cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))


def csrf_cookie():
    return next((cookie.value for cookie in cookies if cookie.name == "csrftoken"), "")


def call(path, payload=None, expect=200, csrf=True):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if data is not None and csrf:
        headers["X-CSRFToken"] = csrf_cookie()
    req = urllib.request.Request(base + path, data=data, headers=headers)
    try:
        response = opener.open(req, timeout=8)
    except urllib.error.HTTPError as exc:
        response = exc
    content = json.load(response)
    assert response.status == expect, (path, response.status, expect, content)
    return content


call("csrf")
assert csrf_cookie(), "CSRF cookie must be provisioned"
assert call("me")["authenticated"] is False
assert call("maintenance", expect=401)["error"] == "authentication_required"
# A POST with no CSRF header must be denied even after cookie issuance.
req = urllib.request.Request(
    base + "login",
    data=json.dumps({"username": sys.argv[1], "password": password}).encode(),
    headers={"Content-Type": "application/json"},
)
try:
    opener.open(req, timeout=8)
    raise AssertionError("Login without CSRF header was allowed")
except urllib.error.HTTPError as exc:
    assert exc.code == 403, exc.code

user = call("login", {"username": sys.argv[1], "password": password})
assert user["authenticated"] and "data-maintainer" in user["roles"]
call("csrf")  # Django rotates the token on login.
assert call("me")["authenticated"]
assert call("maintenance")["workspace"] == "Maintenance & Governance"
assert call("sandbox", expect=403)["error"] == "permission_denied"
assert call("sandbox/write", {}, expect=403)["error"] == "permission_denied"
assert call("user-admin", expect=403)["error"] == "permission_denied"
assert call("logout", {})["authenticated"] is False
assert call("maintenance", expect=401)["error"] == "authentication_required"
print("Live same-origin auth/CSRF/roles smoke PASSED.")

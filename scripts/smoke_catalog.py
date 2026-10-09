#!/usr/bin/env python3
"""PLAT-06: real Caddy/Django sessions, all typed catalog URLs; fresh Server empty."""
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

if len(sys.argv) != 2 or not os.environ.get("AI_COMPASS_TEST_PASSWORD"):
    raise SystemExit("Usage: AI_COMPASS_TEST_PASSWORD=... python3 scripts/smoke_catalog.py USERNAME")

base = "http://127.0.0.1:" + os.environ.get("AI_COMPASS_HTTP_PORT", "8080") + "/api/v1/"
kinds = {
    "provider": {"hosting": "cloud", "access": "API", "pricing": "PAYG",
                 "ext": {"custom": [None, "retained"]}},
    "harness": {"interface": "cli", "integrations": ["terminal", "ide"], "ext": {"enabled": True}},
    "framework": {"process": "Plan-Implement-Review", "orchestration": "n8n",
                  "stages": ["plan", "implement", "review"], "ext": {"roles": ["planner", "coder"]}},
}
expected_prefix = {"provider": "prv-", "harness": "hrn-", "framework": "frm-"}


def session():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def call(opener, jar, path, data=None, status=200):
    token = next((c.value for c in jar if c.name == "csrftoken"), "")
    headers = {"Content-Type": "application/json", "X-CSRFToken": token} if data is not None else {}
    request = urllib.request.Request(base + path,
        data=json.dumps(data).encode() if data is not None else None, headers=headers)
    try:
        response = opener.open(request, timeout=12)
    except urllib.error.HTTPError as error:
        response = error
    try:
        body = json.load(response)
    except (ValueError, UnicodeDecodeError):
        body = {"status": response.status}  # Django renders 404 as HTML with DEBUG=False
    assert response.status == status, (path, response.status, status, body)
    return body


def login(opener, jar):
    call(opener, jar, "auth/csrf")
    call(opener, jar, "auth/login", {
        "username": sys.argv[1], "password": os.environ["AI_COMPASS_TEST_PASSWORD"]
    })
    call(opener, jar, "auth/csrf")


first, cookies = session()
second, second_cookies = session()
login(first, cookies)
login(second, second_cookies)

for kind, properties in kinds.items():
    uri = "catalog/" + kind
    assert call(first, cookies, uri)["results"] == [], "Server must not preload Demo fixtures"
    assert call(first, cookies, "catalog/schemas/" + kind)["version"] == 1
    created = call(first, cookies, uri, {
        "name": "Smoke " + kind, "properties": properties
    }, 201)
    ident = created["id"]
    assert ident.startswith(expected_prefix[kind]) and created["revision"] == "r001"
    assert created["schema_version"] == 1 and created["properties"] == properties
    assert call(second, second_cookies, uri)["results"][0]["id"] == ident
    assert call(second, second_cookies, uri + "/" + ident)["properties"] == properties
    revised = call(second, second_cookies, uri + "/" + ident + "/revisions", {
        "expected_revision": "r001", "name": "Revised " + kind
    }, 201)
    assert revised["revision"] == "r002" and revised["properties"] == properties
    versions = call(first, cookies, uri + "/" + ident + "/revisions")["revisions"]
    assert [row["name"] for row in versions] == ["Smoke " + kind, "Revised " + kind]
    assert all(row["properties"] == properties for row in versions)
    assert call(first, cookies, uri + "/" + ident + "/revisions/1")["revision"] == "r001"
    conflict = call(first, cookies, uri + "/" + ident + "/revisions", {
        "expected_revision": "r001", "name": "Stale"
    }, 409)
    assert conflict["error"] == "revision_conflict"
    wrong_kind = "provider" if kind != "provider" else "harness"
    assert call(first, cookies, "catalog/" + wrong_kind + "/" + ident, status=404)["status"] == 404
    assert call(first, cookies, uri, {
        "name": "Invalid", "properties": {"accessible": "yes"}
    }, 400)["error"] == "invalid_catalog_item"

# A framework is only a catalog entry, never an AI Solution or benchmark run.
assert sum(len(call(first, cookies, "catalog/" + kind)["results"]) for kind in kinds) == 3
assert call(first, cookies, "models")["results"]  # prior independent Model smoke created data
call(first, cookies, "auth/logout", {})
call(second, second_cookies, "auth/logout", {})
print("PLAT-06 real Server catalog HTTP smoke: provider/harness/framework, cross-session history, validation and isolation PASS")

#!/usr/bin/env python3
"""Minimal live HTTP smoke of the Model catalog through Django/Caddy sessions.

CI injects AI_COMPASS_TEST_PASSWORD for a dedicated contributor.
"""
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

if len(sys.argv) != 2 or not os.getenv("AI_COMPASS_TEST_PASSWORD"):
    raise SystemExit("Usage: AI_COMPASS_TEST_PASSWORD=... python3 scripts/smoke-models.py USERNAME")

base = "http://127.0.0.1:" + os.getenv("AI_COMPASS_HTTP_PORT", "8080") + "/api/v1/"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def csrf():
    return next((c.value for c in jar if c.name == "csrftoken"), "")


def call(path, data=None, status=200):
    headers = {"Content-Type": "application/json", "X-CSRFToken": csrf()} if data is not None else {}
    request = urllib.request.Request(
        base + path, headers=headers,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
    )
    try:
        response = opener.open(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    payload = json.load(response)
    assert response.status == status, (path, status, response.status, payload)
    return payload


call("auth/csrf")
call("auth/login", {"username": sys.argv[1], "password": os.environ["AI_COMPASS_TEST_PASSWORD"]})
call("auth/csrf")  # CSRF cookie rotates at login.

schema = call("models/schema")
assert schema["type"] == "model" and schema["version"] == 1

created = call("models", {"name": "Smoke Model", "properties": {"context_window": 12000, "future_flag": 7}}, 201)
public_id = created["id"]
assert public_id.startswith("mdl-") and created["revision"] == "r001"
assert call("models/" + public_id)["name"] == "Smoke Model"

updated = call("models/" + public_id + "/revisions", {"expected_revision": "r001", "name": "Smoke Model v2"}, 201)
assert updated["revision"] == "r002" and updated["id"] == public_id
assert updated["properties"]["future_flag"] == 7
assert call("models/" + public_id + "/revisions/1")["name"] == "Smoke Model"
assert len(call("models/" + public_id + "/revisions")["revisions"]) == 2
assert any(m["id"] == public_id for m in call("models")["results"])
assert call("models/" + public_id + "/revisions", {"expected_revision": "r001", "name": "stale"}, 409)["error"] == "revision_conflict"
assert call("models", {"name": "Invalid", "properties": {"context_window": -1}}, 400)["error"] == "invalid_model"

call("auth/logout", {})
request = urllib.request.Request(base + "models")
try:
    opener.open(request, timeout=10)
    raise AssertionError("Unauthenticated GET was accepted")
except urllib.error.HTTPError as error:
    assert error.code == 401

print("Live Model API create/list/revise/history/schema/RBAC smoke PASSED:", public_id)

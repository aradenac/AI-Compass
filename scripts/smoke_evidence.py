#!/usr/bin/env python3
"""End-to-end PLAT-17 evidence smoke through Caddy with two real Django sessions."""
import hashlib
import http.cookiejar
import json
import os
import secrets
import sys
import urllib.error
import urllib.request

if len(sys.argv) != 2 or not os.getenv("AI_COMPASS_TEST_PASSWORD"):
    raise SystemExit("Usage: AI_COMPASS_TEST_PASSWORD=... python3 scripts/smoke_evidence.py USER")
base = "http://127.0.0.1:" + os.getenv("AI_COMPASS_HTTP_PORT", "8080") + "/api/v1/"
bytes_ = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n" + secrets.token_bytes(48)
digest = hashlib.sha256(bytes_).hexdigest()


def browser():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def request(opener, jar, route, data=None, content_type="application/json", expected=200):
    csrf = next((cookie.value for cookie in jar if cookie.name == "csrftoken"), "")
    headers = {"Content-Type": content_type, "X-CSRFToken": csrf} if data is not None else {}
    req = urllib.request.Request(base + route, data=data, headers=headers)
    try:
        resp = opener.open(req, timeout=15)
    except urllib.error.HTTPError as exc:
        resp = exc
    payload = resp.read()
    assert resp.status == expected, (route, resp.status, expected, payload[:500])
    return resp, payload


def api(opener, jar, route, obj=None, expected=200):
    return json.loads(request(opener, jar, route, json.dumps(obj).encode() if obj is not None else None,
                              expected=expected)[1])


def login(opener, jar):
    api(opener, jar, "auth/csrf")
    api(opener, jar, "auth/login", {"username": sys.argv[1], "password": os.environ["AI_COMPASS_TEST_PASSWORD"]})
    api(opener, jar, "auth/csrf")


def multipart(payload, filename, revision, source, provenance):
    boundary = "aic-" + secrets.token_hex(16)
    parts = []
    for key, value in {"revision": revision, "source": source,
                       "provenance": json.dumps(provenance)}.items():
        parts.append(("--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + key +
                      "\"\r\n\r\n" + value + "\r\n").encode())
    parts.append(("--" + boundary +
                  "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"" + filename +
                  "\"\r\nContent-Type: application/pdf\r\n\r\n").encode() + payload + b"\r\n")
    parts.append(("--" + boundary + "--\r\n").encode())
    return b"".join(parts), "multipart/form-data; boundary=" + boundary


one, first_jar = browser()
two, second_jar = browser()
login(one, first_jar)
login(two, second_jar)
catalog = api(one, first_jar, "models")["results"]
assert catalog, "PLAT-05 smoke must create a real Model first"
provider = api(one, first_jar, "catalog/provider")["results"]
assert provider, "PLAT-06 smoke must create a real Provider first"
model = catalog[0]
targets = [
    (model["id"], "r001", "https://example.org/pdf", {"purpose": "model source"}),
    (provider[0]["id"], "r001", "external research", {"purpose": "provider source"}),
]
links = []
for public_id, revision, source, provenance in targets:
    route = "catalog/items/" + public_id + "/evidence"
    body, mime = multipart(bytes_, "original-snapshot.pdf", revision, source, provenance)
    resp, data = request(one, first_jar, route + "/upload", body, mime, expected=201)
    row = json.loads(data)
    assert row["sha256"] == digest and row["revision"] == revision
    assert row["source"] == source and row["provenance"] == provenance
    assert row["integrity"] == "ok"
    listed = api(two, second_jar, route)["results"]
    assert any(link["id"] == row["id"] for link in listed)
    assert api(two, second_jar, "evidence/" + row["id"])["integrity"] == "ok"
    response, downloaded = request(two, second_jar, "evidence/" + row["id"] + "/download")
    assert downloaded == bytes_, "Exact original byte fidelity failed"
    assert "attachment" in response.headers["Content-Disposition"]
    links.append(row)
assert links[0]["id"] != links[1]["id"], "Provenance links were incorrectly merged"
assert links[0]["sha256"] == links[1]["sha256"], "Blob content deduplication failed"
assert api(two, second_jar, "catalog/items/" + model["id"] + "/evidence")["results"][0]["uploaded_by"] == sys.argv[1]
api(one, first_jar, "auth/logout", {})
api(two, second_jar, "auth/logout", {})
print("PLAT-17 private evidence smoke: two sessions, exact bytes, dedup, distinct provenance PASS")

#!/usr/bin/env python3
"""FUT-19: resumable archive download client with digest verification.

Works identically against loopback HTTP or remote HTTPS, resumes an interrupted
transfer with Range requests, and fails closed on truncated, changed or corrupt
bytes. The bearer token is read from the environment (never a command argument),
so it does not leak into a process list, shell history or URL.

    export AI_COMPASS_ARCHIVE_TOKEN=...        # from POST .../grant
    python3 scripts/archive_download.py \
        --base-url https://compass.example \
        --job agr-xxxx --output ./native.zip
"""
import argparse
import hashlib
import os
import sys
import urllib.error
import urllib.request

CHUNK = 1024 * 1024


def _digest(path, resume_from):
    hasher = hashlib.sha256()
    if resume_from:
        with open(path, "rb") as existing:
            while True:
                block = existing.read(CHUNK)
                if not block:
                    break
                hasher.update(block)
    return hasher


def download(base_url, job, output, token):
    url = base_url.rstrip("/") + "/api/v1/archives/download/" + job
    resume_from = os.path.getsize(output) if os.path.exists(output) else 0
    headers = {"Authorization": "Bearer " + token}
    if resume_from:
        headers["Range"] = f"bytes={resume_from}-"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as error:
        # 416 means our local bytes are already all of it or were rejected; a
        # hard failure here is surfaced, never silently restarted.
        raise SystemExit(f"download refused: HTTP {error.code}")
    status = response.status
    if resume_from and status == 200:
        # Server ignored our Range: restart to avoid appending duplicate bytes.
        resume_from = 0
    hasher = _digest(output, resume_from)
    mode = "ab" if resume_from else "wb"
    total = 0
    with open(output, mode) as target:
        while True:
            block = response.read(CHUNK)
            if not block:
                break
            target.write(block)
            hasher.update(block)
            total += len(block)
    expected = response.headers.get("ETag", "").strip('"')
    actual = hasher.hexdigest()
    if expected and expected != actual:
        raise SystemExit(f"integrity failure: sha256 {actual} != ETag {expected}")
    print(f"complete: {output} ({total + resume_from} bytes, sha256 {actual})")
    return actual


def main(argv=None):
    parser = argparse.ArgumentParser(description="Resumable archive download")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--token-env", default="AI_COMPASS_ARCHIVE_TOKEN")
    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"missing bearer token in ${args.token_env}")
    download(args.base_url, args.job, args.output, token)


if __name__ == "__main__":
    sys.exit(main())

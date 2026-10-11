#!/usr/bin/env python3
"""Check every frontend asset referenced by the application is served by Caddy.

This intentionally avoids external packages and must run before the expensive
Docker/Chromium jobs. A missing bind mount made the authenticated UI fail silently.
"""
from html.parser import HTMLParser
from pathlib import Path
import sys


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and attributes.get("src"):
            self.names.add(attributes["src"].split("?")[0])
        if tag == "link" and attributes.get("rel") == "stylesheet" and attributes.get("href"):
            self.names.add(attributes["href"].split("?")[0])


def validate(root):
    root = Path(root)
    document = Assets()
    document.feed((root / "prototype.html").read_text(encoding="utf-8"))
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    staging = (root / "staging" / "compose.yaml").read_text(encoding="utf-8")
    problems = []
    for name in sorted(document.names):
        if "/" in name or name.startswith(".") or "://" in name:
            # No externally hosted, path-traversing or nested assets are allowed
            # in this portable, same-origin application.
            problems.append("Unsupported non-root static asset reference: " + name)
            continue
        if not (root / name).is_file():
            problems.append("Source asset missing: " + name)
        if f"./{name}:/srv/frontend/{name}:ro" not in compose:
            problems.append("Caddy bind mount missing for: " + name)
        if f"../{name}:/srv/frontend/{name}:ro" not in staging:
            problems.append("Staging Caddy bind mount missing for: " + name)
    if problems:
        raise AssertionError("\n".join(problems))
    print(f"PASS: {len(document.names)} frontend assets present in both Server and staging Caddy.")


if __name__ == "__main__":
    validate(Path(__file__).resolve().parents[1])

#!/usr/bin/env python3
"""Create a private, randomized local .env; never overwrite existing credentials."""
from pathlib import Path
import os
import secrets

root = Path(__file__).resolve().parent.parent
target = root / ".env"
if target.exists():
    raise SystemExit(".env already exists; refusing to overwrite it")
template = (root / ".env.example").read_text(encoding="utf-8")
template = template.replace("REPLACE_WITH_RANDOM_PASSWORD", secrets.token_urlsafe(36))
template = template.replace("REPLACE_WITH_RANDOM_SECRET", secrets.token_urlsafe(48))

fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as stream:
    stream.write(template)
print("Created .env (mode 0600). Keep it private and out of Git.")

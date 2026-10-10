#!/usr/bin/env python3
"""Host-side preflight: validates startup profile plus matching real TLS certificate/private key.

Run from the checkout, before starting either deployment. No network, cloud or secrets logged.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import ssl
import sys

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("config.deployment_profiles",
                                            ROOT / "backend/config/deployment_profiles.py")
# Django is installed in the API container in production; the host-side preflight
# must not require Django just to inspect its .env. Install Django when running this CLI.
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def read_env(path):
    result = {}
    for row in path.read_text(encoding="utf-8").splitlines():
        row = row.strip()
        if not row or row.startswith("#"):
            continue
        if "=" not in row:
            raise ValueError("Invalid .env format")
        key, val = row.split("=", 1)
        result[key.strip()] = val.strip().strip('"').strip("'")
    return result


def preflight(env, directory):
    config = module.configuration(env)
    if config["profile"] == "development":
        return config
    certificate = env.get("AI_COMPASS_LAN_CERT", "")
    key = env.get("AI_COMPASS_LAN_KEY", "")
    if not certificate or not key:
        raise ValueError("LAN requires both explicit TLS certificate and private key")
    cert_path, key_path = (Path(x) if Path(x).is_absolute() else directory / x
                           for x in (certificate, key))
    if not cert_path.is_file() or not key_path.is_file():
        raise ValueError("LAN certificate or private key does not exist")
    if key_path.is_symlink() or cert_path.is_symlink():
        raise ValueError("LAN credentials must not use symlinks")
    if key_path.stat().st_mode & 0o077:
        raise ValueError("LAN private key must not be accessible to group/other")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert_path), str(key_path))
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    try:
        data = read_env(args.env)
        # Runtime environment cannot relax the on-disk LAN preflight values.
        checked = preflight(data, args.env.parent)
        print("Deployment preflight: %s profile configuration validated" % checked["profile"])
        return 0
    except Exception as exc:
        print("Deployment preflight refused: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

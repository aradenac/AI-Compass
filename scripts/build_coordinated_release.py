#!/usr/bin/env python3
"""FUT-01: deterministic frontend bundle and fail-closed coordinated release manifest.

Generate only after the PLAT-32 smoke evidence is emitted from the same CI run.
A manifest is NOT a production approval: PLAT's manual gates remain NO-GO.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

SCHEMA = "ai-compass/coordinated-release@1"
VERSION_SCHEMA = "ai-compass/component-versions@1"
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")


class ReleaseError(ValueError):
    pass


def demand(ok, message):
    if not ok:
        raise ReleaseError(message)


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def read_safe(root, name):
    p = root / name
    demand(p.is_file() and not p.is_symlink(), "Missing/unsafe release input: " + str(p))
    demand(p.resolve().is_relative_to(root.resolve()), "Escaped release source root: " + name)
    return p.read_bytes()


def frontend_paths(root):
    # Compose's static mounts are the single source of truth for deployed
    # frontend assets until FUT-03 introduces a standalone shared build.
    compose = read_safe(root, "compose.yaml").decode("utf-8")
    paths = set(re.findall(
        r"^\s*-\s+\./([a-zA-Z0-9_.-]+):/srv/frontend/[a-zA-Z0-9_.-]+:ro\s*$",
        compose, flags=re.MULTILINE))
    demand({"prototype.html", "model-catalog.js", "server-mode.js"} <= paths,
           "Missing expected deployed frontend mounts")
    demand(len(paths) >= 15, "Incomplete frontend deployment asset list")
    return sorted(paths)


def zip_frontend(root, files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, strict_timestamps=True) as archive:
        for name in files:
            info = zipfile.ZipInfo("frontend/" + name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 << 16)
            archive.writestr(info, read_safe(root, name), compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)
    return output.getvalue()


def backend_hashes(root):
    folder = root / "backend"
    demand(folder.is_dir() and not folder.is_symlink(), "Missing backend source directory")
    files = {}
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
            continue
        rel = path.relative_to(root).as_posix()
        files[rel] = digest(read_safe(root, rel))
    demand("backend/Dockerfile" in files and "backend/requirements.txt" in files,
           "Incomplete backend build inputs")
    return files


def validate_evidence(report, commit, repository, run_id):
    demand(report.get("schema") == "ai-compass/release-acceptance@1",
           "Missing/incorrect PLAT-32 acceptance report")
    source = report.get("source") or {}
    expected = "https://github.com/%s/actions/runs/%s" % (repository, run_id)
    demand(source.get("commit") == commit and source.get("repository") == repository
           and source.get("workflow_run") == expected,
           "CI acceptance evidence refers to a different commit/repository/run")
    demand(report.get("automated", {}).get("status") == "passed",
           "Automated release acceptance has not passed")
    demand(len(report.get("automated", {}).get("checks", {})) >= 8
           and all(x.get("status") == "passed" for x in
                   report["automated"]["checks"].values()),
           "Missing/failed acceptance checks")
    recovery = report["automated"].get("recovery", {})
    demand(re.fullmatch(r"[0-9a-f]{64}", recovery.get("drill_report_sha256", "")) is not None
           and recovery.get("authenticated_original_download") == "passed",
           "Verified recovery proof missing")
    demand(report.get("decision") == "NO_GO"
           and all(v == "not_evidenced" for v in
                   report.get("manual_release_gates", {}).values())
           and len(report.get("manual_release_gates", {})) >= 3,
           "Do not fabricate production approval in release manifest")
    return source


def build(root, out, evidence, commit, repository, run_id, backend_image,
          backend_packages):
    demand(COMMIT.fullmatch(commit) is not None, "Invalid source commit")
    demand(re.fullmatch(r"\d+", run_id) is not None, "Invalid CI run identity")
    demand(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is not None,
           "Invalid repository identity")
    demand(SHA256.fullmatch(backend_image) is not None,
           "Backend must be a content-addressed sha256 Docker image ID")
    versions = json.loads(read_safe(root, "release/versions.json"))
    demand(versions.get("schema") == VERSION_SCHEMA and versions.get("api_major") == 1
           and versions.get("api_min_major") == 1
           and versions.get("api_max_major") == 1, "Unsupported component/API version manifest")
    for key in ("release", "frontend", "backend"):
        demand(isinstance(versions.get(key), str)
               and re.fullmatch(r"\d+\.\d+\.\d+", versions[key]) is not None,
               "Invalid or missing component version: " + key)
    api = read_safe(root, "backend/config/release_contract.py")
    demand(b'API_MAJOR = 1' in api and b'API_MIN_MAJOR = 1' in api
           and b'API_MAX_MAJOR = 1' in api,
           "Release declaration mismatches Server contract")
    evidence_bytes = evidence.read_bytes()
    report = json.loads(evidence_bytes)
    validate_evidence(report, commit, repository, run_id)
    package_bytes = backend_packages.read_bytes()
    demand(bool(package_bytes.strip()) and b"django==" in package_bytes.lower()
           and b"psycopg==" in package_bytes.lower(),
           "Missing installed backend dependency inventory (pip freeze)")
    frontend = frontend_paths(root)
    archive_bytes = zip_frontend(root, frontend)
    frontend_files = {f: digest(read_safe(root, f)) for f in frontend}
    backend_files = backend_hashes(root)
    src_hash = digest(canonical(backend_files))
    manifest = {
        "schema": SCHEMA,
        "release_id": "r%s+%s" % (versions["release"], commit[:12]),
        "source": {"repository": repository, "commit": commit, "ci_run_id": run_id,
                   "ci_url": report["source"]["workflow_run"]},
        "components": {
            "frontend": {"version": versions["frontend"],
                         "artifact": "frontend.zip", "artifact_sha256": digest(archive_bytes),
                         "files": frontend_files,
                         "static_bundle": "Compose-mounted frontend sources"},
            "backend": {"version": versions["backend"],
                        "image_id": backend_image, "source_digest": src_hash,
                        "files": backend_files,
                        "pip_freeze_artifact": "backend-packages.txt",
                        "pip_freeze_sha256": digest(package_bytes)},
        },
        "compatibility": {
            "api_major": 1, "supported_client_api_majors": [1],
            "django_migration_snapshot_sha256": digest(canonical({
                name: sha for name, sha in backend_files.items()
                if "/migrations/" in name and name.endswith(".py")
            })),
            "archive_contract": "PLAT native logical and coordinated full recovery",
            "registered_staging_migration": report["automated"]["staging_rejections"]["migration_key"],
        },
        "evidence": {"PLAT-32": "release-acceptance.json",
                     "acceptance_sha256": digest(evidence_bytes),
                     "recovery_sha256": report["automated"]["recovery"]["drill_report_sha256"]},
        "decision": "NO_GO",
        "manual_release_gates": report["manual_release_gates"],
    }
    notes = "\n".join([
        "# AI Compass — coordinated release " + manifest["release_id"],
        "",
        "Source: %s @ %s" % (repository, commit),
        "Frontend: %s (frontend.zip SHA-256 %s)" % (versions["frontend"], digest(archive_bytes)),
        "Backend: %s (OCI image ID %s)" % (versions["backend"], backend_image),
        "API compatibility: major v1, backward-compatible for pre-existing v1 consumers.",
        "Django migration snapshot: " + manifest["compatibility"]["django_migration_snapshot_sha256"],
        "Installed Python packages: backend-packages.txt (SHA-256 " + digest(package_bytes) + ")",
        "Tests: PLAT-32 automated smoke passed; " + report["source"]["workflow_run"],
        "Recovery: independently verified original DB+blob drill (report SHA-256 " +
        report["automated"]["recovery"]["drill_report_sha256"] + ").",
        "Staging migration: " + manifest["compatibility"]["registered_staging_migration"],
        "",
        "**Production decision: NO-GO.** Real browser inspection, recovery rehearsal on",
        "the intended deployment and accountable operator sign-off remain mandatory.",
        "Do not promote a staging DB, infer production readiness from CI, or rebuild",
        "different images under the same coordinated release identifier.",
        "",
    ]) + "\n"
    demand(not out.exists() or out.is_dir(), "Release output destination is not a directory")
    out.mkdir(parents=True, exist_ok=True)
    (out / "frontend.zip").write_bytes(archive_bytes)
    (out / "backend-packages.txt").write_bytes(package_bytes)
    (out / "release-acceptance.json").write_bytes(evidence_bytes)
    (out / "manifest.json").write_bytes(canonical(manifest))
    (out / "release-notes.md").write_text(notes, encoding="utf-8")
    verify(root, out)
    return manifest


def verify(root, out):
    manifest = json.loads(read_safe(out, "manifest.json"))
    demand(manifest.get("schema") == SCHEMA and manifest.get("decision") == "NO_GO",
           "Invalid release manifest or unsafe approval claim")
    source = manifest.get("source") or {}
    validate_evidence(json.loads(read_safe(out, "release-acceptance.json")),
                      source.get("commit"), source.get("repository"), source.get("ci_run_id"))
    demand(digest(read_safe(out, "release-acceptance.json")) ==
           manifest["evidence"]["acceptance_sha256"], "Acceptance evidence changed")
    frontend = manifest["components"]["frontend"]
    archive = read_safe(out, frontend["artifact"])
    demand(digest(archive) == frontend["artifact_sha256"], "Frontend bundle was modified")
    demand(frontend["files"] == {n: digest(read_safe(root, n)) for n in frontend_paths(root)},
           "Frontend sources no longer match manifest")
    demand(archive == zip_frontend(root, frontend_paths(root)),
           "Frontend artifact is not reproducible from pinned sources")
    backend = manifest["components"]["backend"]
    demand(SHA256.fullmatch(backend.get("image_id", "")) is not None,
           "Unpinned backend image")
    demand(backend["files"] == backend_hashes(root)
           and backend["source_digest"] == digest(canonical(backend["files"])),
           "Backend source drift")
    demand(digest(read_safe(out, backend["pip_freeze_artifact"])) ==
           backend["pip_freeze_sha256"], "Backend dependency inventory modified")
    demand("**Production decision: NO-GO.**" in
           read_safe(out, "release-notes.md").decode("utf-8"),
           "Release notes must not omit operational approval blockers")
    demand(source.get("commit") and COMMIT.fullmatch(source["commit"]),
           "Unverified source commit")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "verify"])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--repository")
    parser.add_argument("--run-id")
    parser.add_argument("--backend-image")
    parser.add_argument("--backend-packages", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            demand(all((args.evidence, args.commit, args.repository, args.run_id,
                        args.backend_image, args.backend_packages)),
                   "Build requires evidence, commit, run, backend image and pip inventory")
            result = build(args.root, args.output, args.evidence,
                           args.commit, args.repository, args.run_id,
                           args.backend_image, args.backend_packages)
        else:
            result = verify(args.root, args.output)
        print(json.dumps({"release": result["release_id"],
                          "decision": result["decision"], "status": "verified"}))
        return 0
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as error:
        print("RELEASE BLOCKED: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

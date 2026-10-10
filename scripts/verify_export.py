#!/usr/bin/env python3
"""Verify AI Compass native archive v1 without Django, credentials or a server.

Usage: python3 scripts/verify_export.py /path/to/ai-compass-native-v1.zip
Fails closed on missing members, corrupt original bytes, invalid references or
truncated/inconsistent record counts; never extracts archive contents.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
import zipfile

FORMAT = "ai-compass-native"
VERSION = 1
MAX_MEMBERS = 10000
MAX_BYTES = 2 * 1024 ** 3
MAX_LINE = 8 * 1024 * 1024


class VerificationError(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise VerificationError(reason)


def _json_member(archive, name, limit=8 * 1024 * 1024):
    info = archive.getinfo(name)
    _require(info.file_size <= limit, "Oversized JSON member: " + name)
    try:
        with archive.open(info) as reader:
            return json.loads(reader.read().decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise VerificationError("Invalid JSON member: " + name) from exc


def verify(path):
    archive_digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            archive_digest.update(chunk)

    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            _require(len(infos) <= MAX_MEMBERS and len(names) == len(set(names)),
                     "Too many or duplicate archive entries")
            _require("manifest.json" in names and "schema.json" in names
                     and "subjects.json" in names, "Missing control files")
            _require(sum(x.file_size for x in infos) <= MAX_BYTES,
                     "Archive exceeds maximum uncompressed size")
            for item in infos:
                segments = item.filename.split("/")
                _require(
                    re.fullmatch(r"[a-zA-Z0-9_.\/-]+", item.filename) is not None
                    and all(p not in ("", ".", "..") for p in segments)
                    and not item.is_dir()
                    and not item.flag_bits & 1
                    and stat.S_IFMT(item.external_attr >> 16) != stat.S_IFLNK,
                    "Unsafe ZIP entry",
                )

            manifest = _json_member(archive, "manifest.json")
            _require(isinstance(manifest, dict) and manifest.get("format") == FORMAT
                     and manifest.get("version") == VERSION
                     and manifest.get("complete") is True
                     and manifest.get("snapshot", {}).get("isolation") == "repeatable_read",
                     "Unsupported or incomplete native archive")
            declared = manifest.get("files")
            _require(isinstance(declared, dict) and
                     set(declared) == set(names) - {"manifest.json"},
                     "Missing, extra or undeclared archive member")
            for name in sorted(declared):
                declared_item = declared[name]
                info = archive.getinfo(name)
                _require(isinstance(declared_item, dict)
                         and isinstance(declared_item.get("sha256"), str)
                         and declared_item.get("size") == info.file_size,
                         "Invalid member declaration: " + name)
                checksum = hashlib.sha256()
                with archive.open(info) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        checksum.update(chunk)
                _require(checksum.hexdigest() == declared_item["sha256"],
                         "SHA-256 mismatch: " + name)

            schema = _json_member(archive, "schema.json")
            _require(isinstance(schema, dict) and schema.get("format") == FORMAT
                     and schema.get("version") == VERSION
                     and isinstance(schema.get("models"), list), "Invalid archive schema")
            subjects = _json_member(archive, "subjects.json")
            _require(isinstance(subjects, dict) and isinstance(subjects.get("users"), list),
                     "Invalid subject directory")
            users = set()
            for user in subjects["users"]:
                _require(isinstance(user, dict) and set(user) ==
                         {"id", "username", "roles", "is_active"}
                         and isinstance(user["roles"], list), "Invalid exported user fields")
                uid = str(user["id"])
                _require(uid not in users, "Duplicate identity")
                users.add(uid)
            _require(manifest.get("subjects") == len(users),
                     "User count mismatch")

            indexed = {"auth.user": users}
            pending = []
            counts = {}
            models = schema["models"]
            _require(len(models) == len({m.get("model") for m in models}),
                     "Duplicate model declaration")
            total = 0
            for spec in models:
                _require(isinstance(spec, dict), "Invalid model declaration")
                label, member = spec.get("model"), spec.get("path")
                _require(isinstance(label, str) and
                         re.fullmatch(r"config\.[a-z0-9_]+", label) is not None
                         and member == "records/" + label + ".ndjson"
                         and member in declared
                         and isinstance(spec.get("count"), int)
                         and spec["count"] >= 0
                         and isinstance(spec.get("relations"), list),
                         "Invalid model path/count")
                rows = set()
                count = 0
                with archive.open(member) as stream:
                    while True:
                        line = stream.readline(MAX_LINE + 1)
                        if not line:
                            break
                        _require(len(line) <= MAX_LINE and line.endswith(b"\n"),
                                 "Truncated or oversized NDJSON record")
                        try:
                            row = json.loads(line)
                        except (ValueError, UnicodeError) as exc:
                            raise VerificationError("Invalid NDJSON record") from exc
                        _require(isinstance(row, dict) and row.get("model") == label
                                 and isinstance(row.get("fields"), dict)
                                 and row.get("pk") is not None, "Invalid typed record")
                        pk = str(row["pk"])
                        _require(pk not in rows, "Duplicate primary key: " + label)
                        rows.add(pk)
                        for relation in spec["relations"]:
                            _require(isinstance(relation, dict)
                                     and isinstance(relation.get("field"), str)
                                     and isinstance(relation.get("target"), str)
                                     and isinstance(relation.get("uses_pk"), bool),
                                     "Invalid FK declaration")
                            reference = (row["pk"] if relation["uses_pk"] else
                                         row["fields"].get(relation["field"]))
                            if reference is not None:
                                pending.append((label, pk, relation["target"], str(reference)))
                        count += 1
                _require(count == spec["count"], "Record count mismatch: " + label)
                counts[label] = count
                total += count
                indexed[label] = rows
            _require(total == manifest.get("record_count"), "Total record count mismatch")
            for source_model, source_id, target_model, target_id in pending:
                _require(target_model in indexed and target_id in indexed[target_model],
                         "Unresolved FK: " + source_model + "/" + source_id
                         + " -> " + target_model + "/" + target_id)

            blob_member_prefix = "evidence/blobs/"
            expected_blobs = {}
            blob_label = "config.evidenceblob"
            if blob_label in indexed:
                member = "records/" + blob_label + ".ndjson"
                with archive.open(member) as reader:
                    for line in reader:
                        row = json.loads(line)
                        digest = str(row["pk"])
                        _require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
                                 "Invalid content-addressed evidence key")
                        expected_blobs[blob_member_prefix + digest] = (
                            digest, row["fields"]["size"])
            actual_blobs = {name for name in declared if name.startswith(blob_member_prefix)}
            _require(actual_blobs == set(expected_blobs)
                     and manifest.get("evidence_blob_count") == len(expected_blobs),
                     "Missing or untracked original evidence blobs")
            for member, (digest, length) in expected_blobs.items():
                _require(declared[member]["sha256"] == digest
                         and declared[member]["size"] == length,
                         "Evidence payload hash/size differs from immutable metadata")
            return {"status": "verified", "format": FORMAT, "version": VERSION,
                    "archive_sha256": archive_digest.hexdigest(),
                    "records": total, "models": counts,
                    "original_evidence_blobs": len(expected_blobs)}
    except (zipfile.BadZipFile, KeyError, TypeError, OverflowError) as error:
        raise VerificationError("Malformed or incomplete native archive") from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(args.archive)
    except (VerificationError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""PLAT-33 external-source intake preflight: read-only, no business DB access.

This is NOT an import adapter or approval for production. Format and target
entity must be chosen from an actual permitted real source before import code
can be implemented. No Demo or native archive is ever accepted as a source.
"""
import argparse
import collections
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 2000
MAX_FIELDS = 100
MAX_LINE = 128 * 1024
SCHEMA = "ai-compass/external-intake-preflight@1"
FORMATS = ("csv", "jsonl")
CLASSIFICATIONS = ("public", "internal", "confidential")


class PreflightError(ValueError):
    pass


def ensure(value, message):
    if not value:
        raise PreflightError(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        ensure(key not in result, "Duplicate JSON property: " + key)
        result[key] = value
    return result


def _type(value):
    if value is None or value == "":
        return "missing"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is float:
        return "number"
    if type(value) is str:
        return "string"
    if type(value) is list:
        return "array"
    return "object"


def _source_bytes(path):
    source = Path(path).expanduser()
    ensure(source.is_file() and not source.is_symlink(),
           "Supply one existing regular, non-symlink local source file")
    fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        st = os.fstat(fd)
        ensure(stat.S_ISREG(st.st_mode) and 0 < st.st_size <= MAX_BYTES,
               "Source must be a non-empty regular file of at most 10 MiB")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
        ensure(len(data) <= MAX_BYTES and len(data) == st.st_size,
               "Source changed during reading or exceeds limit")
        ensure(not data.startswith(b"PK\x03\x04"),
               "Native/ZIP archives are not external onboarding sources")
        return data
    finally:
        os.close(fd)


def _rows_csv(text):
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, None)
        ensure(header, "CSV header must not be empty")
        ensure(len(header) <= MAX_FIELDS, "Too many columns")
        ensure(all(isinstance(k, str) and k and len(k) <= 120
                   and k == k.strip() for k in header),
               "CSV header has empty, whitespace or overly long fields")
        ensure(len(set(header)) == len(header), "Duplicate CSV column names")
        def records():
            for row in reader:
                ensure(len(row) == len(header), "CSV row has missing/extra columns")
                yield dict(zip(header, row))
        return header, records()
    except (csv.Error, UnicodeError) as error:
        raise PreflightError("Invalid CSV header: " + str(error)) from error


def _rows_jsonl(text):
    def records():
        for line_number, line in enumerate(text.splitlines(), 1):
            ensure(line.strip(), "Blank JSONL row " + str(line_number))
            ensure(len(line.encode("utf-8")) <= MAX_LINE,
                   "Oversized JSONL row " + str(line_number))
            try:
                obj = json.loads(line, object_pairs_hook=_unique_object,
                                 parse_constant=lambda token: (_ for _ in ()).throw(
                                     PreflightError("Nonfinite JSON number: " + token)))
            except (json.JSONDecodeError, UnicodeError) as error:
                raise PreflightError("Invalid JSONL at line " + str(line_number)) from error
            ensure(isinstance(obj, dict), "Every JSONL row must be a flat object")
            ensure(len(obj) <= MAX_FIELDS, "Too many JSONL fields")
            for key in obj:
                ensure(isinstance(key, str) and key and len(key) <= 120
                       and key == key.strip(), "Invalid JSONL field name")
            ensure(obj.get("mode") != "demo" and "localStorage" not in obj,
                   "Demo/localStorage payloads are forbidden")
            yield obj
    return None, records()


def discover(path, *, format, origin, owner, permission_basis, classification,
             real_source_attested=False):
    ensure(format in FORMATS, "Choose explicitly one recognized source format")
    ensure(classification in CLASSIFICATIONS, "Invalid confidentiality classification")
    for title, value, upper in (
        ("origin", origin, 600), ("owner", owner, 160),
        ("permission_basis", permission_basis, 600),
    ):
        ensure(isinstance(value, str) and 4 <= len(value.strip()) <= upper,
               "A documented " + title + " is mandatory")
    ensure(real_source_attested is True,
           "A named operator must attest an authorized real external source")
    meta = " ".join([origin, owner, permission_basis, Path(path).name]).lower()
    ensure(not re.search(r"(?:^|[^a-z])(demo|localstorage|synthetic|fixture)(?:[^a-z]|$)", meta),
           "Demo/fixture source is not eligible for real data onboarding")
    raw = _source_bytes(path)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise PreflightError("Input must be UTF-8") from error
    ensure("\x00" not in text, "NUL bytes are forbidden")
    ensure(max((len(line.encode("utf-8")) for line in text.splitlines()), default=0) <= MAX_LINE,
           "Source has an oversized line")
    fields, rows = _rows_csv(text) if format == "csv" else _rows_jsonl(text)
    observed = collections.defaultdict(collections.Counter)
    signatures = set()
    duplicates = 0
    count = 0
    known = set(fields or [])
    for item in rows:
        count += 1
        ensure(count <= MAX_ROWS, "Source exceeds 2000 rows: provide a bounded representative sample")
        signature = hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False,
                                            separators=(",", ":")).encode("utf-8")).hexdigest()
        if signature in signatures:
            duplicates += 1
        signatures.add(signature)
        known.update(item)
        ensure(len(known) <= MAX_FIELDS, "Source has more than 100 distinct fields")
        for key in known:
            pass
        for key, value in item.items():
            observed[key][_type(value)] += 1
    ensure(count > 0, "Source must contain at least one row")
    keys = sorted(known)
    for key in keys:
        observed[key]["missing"] += count - sum(observed[key].values())
    return {
        "schema": SCHEMA,
        "status": "source_discovered_mapping_pending",
        "approved_for_apply": False,
        "production_ready": False,
        "source": {
            "origin": origin.strip(), "owner": owner.strip(),
            "permission_basis": permission_basis.strip(),
            "classification": classification,
            "format": format, "sha256": digest, "bytes": len(raw),
            "real_source_attestation": "operator-declared, not independently verified",
        },
        "inventory": {
            "rows": count, "identical_duplicate_rows": duplicates,
            "fields": [{"name": name,
                        "observed_types": dict(sorted(observed[name].items())),
                        "missing_count": observed[name]["missing"]}
                       for name in keys],
        },
        "mapping_gate": {
            "target_business_type": None,
            "stable_source_key_field": None,
            "selected_adapter": None,
            "source_samples_reviewed": False,
            "deployment_acceptance": "not_evidenced",
            "reason": "Requires explicit owner-approved real source/type/key mapping and separately validated deployment",
        },
        "constraints": [
            "No database connection or mutation",
            "No row values stored in this report",
            "Native AI Compass archives and Demo fixtures are never external imports",
            "This inventory is not a dry-run of target-schema validation",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True)
    parser.add_argument("--format", choices=FORMATS, required=True)
    parser.add_argument("--origin", required=True, help="Actual real-source identity")
    parser.add_argument("--owner", required=True, help="Responsible owner of the source")
    parser.add_argument("--permission-basis", required=True,
                        help="Why importing this source would be permitted")
    parser.add_argument("--classification", choices=CLASSIFICATIONS, required=True)
    parser.add_argument("--real-source-attested", action="store_true",
                        help="Operator attests this is not Demo/synthetic/customer-unapproved data")
    args = parser.parse_args(argv)
    try:
        report = discover(args.file, format=args.format, origin=args.origin,
                          owner=args.owner, permission_basis=args.permission_basis,
                          classification=args.classification,
                          real_source_attested=args.real_source_attested)
    except (PreflightError, OSError, csv.Error) as error:
        print("EXTERNAL INTAKE REFUSED: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

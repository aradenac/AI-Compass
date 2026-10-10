# PLAT-33 — External real-data onboarding: source discovery

**Status:** first safe source-discovery tool delivered. **No real source, business
entity, origin permissions or production deployment is approved yet.** This is
a non-mutating prerequisite for PLAT-33, **not** a completed import adapter,
business-level dry run or ticket acceptance. #33 remains open until one
concrete source and object type are chosen and end-to-end imported.

The empty Server has NO fake Demo business objects. Native AI Compass
archives are handled by PLAT-31 for isolated restoration, **not** by the
external import pipeline. Neither Demo localStorage nor historical recovery
snapshots may be used as external real business sources.

## Step 1 — Obtain an approved representative real source

The source owner must identify:

- Exact source system, origin URL/export identifier and contact/ownership
  (not a guessed or scrape-derived source);
- Written permission/usage scope and data classification; appropriate
  redaction for personal/confidential fields;
- An actual bounded CSV or newline-delimited JSON (JSONL) representative
  sample, including edge cases and missing values; never check real source
  data, passwords or customer names into Git or attach them to public CI;
- The **first one** intended target business object type, the source's
  stable per-record key, update/conflict rules, known/unknown field mapping
  and expected evidence/provenance policy;
- A genuinely accepted operational Server deployment and reviewer.

Do not fabricate sources or copy the prototype's seeded Demo records to
satisfy this step. The input format is explicitly selected at discovery
time; a real domain import adapter can be designed only after source
ownership, representative samples and target type have been approved.

## Step 2 — Perform local read-only source discovery

On a trusted machine with the actual permitted source exported locally:

    python3 scripts/external_source_preflight.py \
      --file /private/location/authorized-export.csv \
      --format csv \
      --origin "https://company.example/source-system/export" \
      --owner "Responsible data owner" \
      --permission-basis "Reference the internal data sharing approval" \
      --classification confidential \
      --real-source-attested \
      > /private/location/source-intake-inventory.json

Use \`--format jsonl\` for newline-delimited JSON objects, not an arbitrary
single JSON document or an AI Compass ZIP. The tool never connects to
PostgreSQL, authenticates a website, applies an import or creates a
CatalogItem. It reads **at most 10 MiB and 2,000 rows**. Filenames, owner
and source are explicit, and a human must attest they are real and
authorized. This declaration is not independently verified.

The output is a reviewable source inventory containing the original
file's SHA-256, byte and row counts, field names, observed type counts,
missing-value counts and identical-duplicate-row count. **No source record
values** are included in the JSON. Keep the report private: field names
and source origin can still be sensitive. The output also includes these
machine-enforced, explicit gates:

    "status": "source_discovered_mapping_pending"
    "approved_for_apply": false
    "production_ready": false
    "mapping_gate": {
      "target_business_type": null,
      "stable_source_key_field": null,
      "selected_adapter": null,
      ...
    }

Malformed CSV/JSONL, repeated columns/JSON keys, unsafe or oversized
files, symlinks, Demo/fixture identifiers and ZIP data are refused.
A successful inventory is NOT evidence that its semantic business mapping,
authorization, validity or production readiness are approved.

## Step 3 — Future implementation, NOT yet authorized

When the real data owner has approved the format, target entity and stable
source key, implement one narrow immutable import adapter with:
read-only **target-schema-aware** dry-run, stable external-key mapping,
row-level error and duplicate reporting, explicit reviewed apply, immutable
new revisions (unchanged rows remain unchanged), exact original evidence
hashes, import batch attribution, permissions and crash-safe retry.
The adapter must not infer unknown values, copy Demo fixtures or silently
merge conflicting records.

**This adapter is not present in this increment.** Do not claim #33
satisfied, do not run an import into a production database before deployment
acceptance and do not close #33 until a selected real-source fixture has
been previewed/applied/retried on the approved target.

## Tests

    python3 -m py_compile scripts/external_source_preflight.py
    python3 -m unittest discover -s scripts -p 'test_external_source_preflight.py' -v

The full GitHub platform smoke CI adds this suite to all existing Demo/
Server migration, staging, recovery and original-data integrity tests.
Tests use synthetic **unit fixtures only**, not a real data source; those
fixtures are never passed into a production importer.

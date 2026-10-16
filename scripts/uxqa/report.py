"""Machine- and human-readable UX-R07 acceptance reports."""
import json
from datetime import datetime, timezone

from . import coverage


def build(records, findings, duration, suite):
    results = {record["name"]: {"result": record["result"],
                                "detail": str(record.get("message", ""))[:200]}
               for record in records}
    matrix = coverage.build(results)
    failed = [record for record in records if record["result"] == "FAIL"]
    return {
        "version": 2,
        "suite": suite,
        "issue": "UX-R07 #126",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if (failed or matrix["unmapped"]) else "PASS",
        "device_scope": "desktop Chromium 1366x900 (mobile/tablet out of scope)",
        "ui_conformance": ("TRACEABLE_20_SCENARIO_COVERAGE; MANUAL_STAGING_AND_AT_NARRATION_"
                           "REQUIRE_SEPARATE_REVIEW"),
        "production_approval": "NO-GO: separate operational gates",
        "checks": records,
        "scenario_coverage": matrix,
        "accessibility_findings": findings,
        "duration_seconds": round(duration, 2),
    }


def write(directory, report):
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    failures = [check for check in report["checks"] if check["result"] == "FAIL"]
    lines = ["# UX-R07 (#126) desktop acceptance — " + report["status"], "",
             f"Real Chromium journeys: **{len(report['checks']) - len(failures)}/"
             f"{len(report['checks'])} passed** in {report['duration_seconds']}s "
             "(desktop 1366×900; Demo and authenticated Server).",
             "",
             "Machine-readable evidence: `report.json`; screenshots and traces are retained "
             "next to it. Screenshots are inspection evidence, **not** approved golden "
             "baselines. Manual staging, screen-reader narration and production approval "
             "remain separate gates → **NO-GO**.", ""]
    lines.extend(["## Checks", "", "| Check | Result | Detail |", "| --- | --- | --- |"])
    for check in report["checks"]:
        detail = str(check.get("message", "")) or json.dumps(check.get("details", {}))
        lines.append(f"| {check['name']} | {check['result']} | "
                     + detail.replace("|", "/")[:220] + " |")
    matrix = report["scenario_coverage"]
    counts = ", ".join(f"{key}: {value}" for key, value in sorted(matrix["counts"].items()))
    lines.extend(["", "## Normative §13 / modal coverage", "",
                  f"Requirements: {counts}. Source: {matrix['source']}", "",
                  "| ID | Status | Requirement | Checks | Note |",
                  "| --- | --- | --- | --- | --- |"])
    for row in matrix["requirements"]:
        note = row.get("reason", "") or ((row.get("results") or [{}])[0].get("detail", ""))
        lines.append(f"| {row['id']} | {row['status']} | {row['title'][:110]} | "
                     + (f"{len(row['results'])}/{len(row['checks'])}"
                        if row["checks"] else "0/0") + " | "
                     + str(note).replace("|", "/")[:200] + " |")
    if matrix["unmapped"]:
        lines.extend(["", "## Traceability break", "",
                      "The coverage registry references checks that did not run, so the "
                      "gate is NOT certified:"])
        for item in matrix["unmapped"]:
            lines.append(f"- {item['requirement']}: {', '.join(item['missing_checks'])}")
    findings = report["accessibility_findings"]
    lines.extend(["", "## Audited accessibility findings (reviewed, not silently green)"])
    if not findings:
        lines.append("- None recorded in this run.")
    else:
        grouped = {}
        for finding in findings:
            grouped.setdefault(finding["kind"], []).append(finding)
        for kind, items in sorted(grouped.items()):
            labels = ", ".join(item["label"] for item in items)
            lines.append(f"- {kind}: {len(items)} view(s) — {labels}")
    lines.extend(["", "## Known limits",
                  "- Desktop Chromium only; no mobile/tablet emulation or responsive matrix.",
                  "- Contrast, screen-reader narration and human visual approval are manual "
                  "review items.",
                  "- Scenarios whose owning implementation is still in flight are reported as "
                  "BLOCKED/PARTIAL with a reason, never as a pass.",
                  "- A green run is not a production GO."])
    (directory / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if report["status"] == "FAIL" else 0

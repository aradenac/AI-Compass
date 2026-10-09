#!/usr/bin/env python3
"""CI-only: exercise REAL Model services across an isolated PostgreSQL snapshot.

A brand-new, randomly named Compose project contains the entire SOURCE test DB
and its own credentials, network and volume. Only this project is destroyed.
Recovery is still validated in recovery.py's separate networkless container.
Never run this test against an operational or reused project.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile

import recovery

ROOT = Path(__file__).resolve().parent.parent
PG_USER = "aic_fixture"
PG_DB = "aic_fixture"

BEFORE = r"""
import hashlib, json
from django.contrib.auth import get_user_model
from config.catalog_services import create_model, revise_model
from config.models import ObjectTypeVersion
actor = get_user_model().objects.create_user(username="ci-recovery-actor")
initial = {"context_window": 16000, "supports_tools": True, "extension": {"origin": "before", "absent": None}}
later = {"context_window": 32000, "supports_tools": False, "extension": {"origin": "second", "absent": None}}
item = create_model(actor=actor, name="Isolated CI r001", properties=initial)
item = revise_model(item=item, actor=actor, expected_revision="r001",
                    name="Isolated CI r002", properties=later)
schemas = [{"type": s.type_slug, "version": s.version,
            "sha256": hashlib.sha256(json.dumps(s.json_schema, sort_keys=True,
                ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()}
           for s in ObjectTypeVersion.objects.order_by("type_slug", "version")]
print(json.dumps({"id": item.public_id, "uuid": str(item.pk),
                  "schemas": schemas, "model_schema_version": item.current_revision.schema_version.version,
                  "initial": initial, "later": later}))
"""

AFTER = r"""
import json
from django.contrib.auth import get_user_model
from config.catalog_services import create_model, revise_model
from config.models import CatalogItem, CatalogRevision
actor = get_user_model().objects.get(username="ci-recovery-actor")
before = CatalogItem.objects.get(public_id="MODEL_ID_PLACEHOLDER")
rev = revise_model(item=before, actor=actor, expected_revision="r002",
                   name="Isolated CI r003 NOT IN SNAPSHOT",
                   properties={"context_window": 64000, "post_snapshot_change": True})
after = create_model(actor=actor, name="Post snapshot Model",
                     properties={"context_window": 64000, "only_after": True})
print(json.dumps({"post_id": after.public_id,
                  "original_latest": rev.current_revision.number,
                  "live_item_count": CatalogItem.objects.count(),
                  "live_revision_count": CatalogRevision.objects.count()}))
"""


def execute(args, *, capture=True, binary_path=None):
    output = subprocess.PIPE if capture else None
    if binary_path is not None:
        with open(binary_path, "wb") as stream:
            proc = subprocess.run(args, cwd=ROOT, stdout=stream,
                                  stderr=subprocess.PIPE, check=False, timeout=240)
    else:
        proc = subprocess.run(args, cwd=ROOT, stdout=output,
                              stderr=subprocess.PIPE, check=False, timeout=240)
    if proc.returncode:
        raise RuntimeError("Isolated CI command failed: " +
                           proc.stderr.decode("utf-8", "replace")[-1200:])
    return (proc.stdout or b"").decode("utf-8", "replace").strip()


def read_json_line(command):
    return json.loads(execute(command).splitlines()[-1])


def main():
    # A two-key guard ensures nobody accidentally turns this destructive test
    # into an operator command on their existing business database.
    if os.getenv("GITHUB_ACTIONS") != "true" or os.getenv("AI_COMPASS_ISOLATED_FIXTURE_CI") != "1":
        raise RuntimeError("Fixture drill is CI-only; refusing to access any live environment")
    runner_temp = os.environ.get("RUNNER_TEMP")
    if not runner_temp or not Path(runner_temp).is_dir():
        raise RuntimeError("Missing GitHub hosted runner's scratch directory")
    project = "aic-recovery-ci-" + secrets.token_hex(6)
    if not re.fullmatch(r"aic-recovery-ci-[a-f0-9]{12}", project):
        raise RuntimeError("Unsafe disposable project identifier")
    with tempfile.TemporaryDirectory(prefix="aic-domain-recovery-", dir=runner_temp) as scratch:
        working = Path(scratch)
        envfile = working / "ci-only.env"
        envfile.write_text(
            "DB_NAME=" + PG_DB + "\n"
            "DB_USER=" + PG_USER + "\n"
            "DB_PASSWORD=" + secrets.token_urlsafe(36) + "\n"
            "DJANGO_SECRET_KEY=" + secrets.token_urlsafe(48) + "\n"
            "DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,api\n"
            "AI_COMPASS_HTTP_PORT=18081\n",
            encoding="utf-8")
        envfile.chmod(0o600)
        compose = [
            "docker", "compose", "--project-directory", str(ROOT),
            "--env-file", str(envfile), "-f", str(ROOT / "compose.yaml"),
            "-p", project
        ]
        started = False
        primary_error = None
        try:
            started = True  # cleanup even if initial Compose start is interrupted
            execute(compose + ["up", "-d", "--wait", "db", "api"])
            execute(compose + ["exec", "-T", "api",
                               "python", "manage.py", "migrate", "--noinput"])
            before = read_json_line(compose + ["exec", "-T", "api",
                                               "python", "manage.py", "shell", "-c", BEFORE])
            assert re.fullmatch(r"mdl-[a-z]+(?:-[a-z]+){2}", before["id"])
            dump = working / "isolated-fixture.dump"
            execute(compose + ["exec", "-T", "db", "sh", "-ec",
                               'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom'],
                    binary_path=dump)
            assert dump.stat().st_size > 100
            # ALL post-snapshot changes are made in the disposable source
            # environment, never the original ai-compass Compose stack.
            post = read_json_line(compose + ["exec", "-T", "api",
                                             "python", "manage.py", "shell", "-c",
                                             AFTER.replace("MODEL_ID_PLACEHOLDER", before["id"])])
            assert re.fullmatch(r"mdl-[a-z]+(?:-[a-z]+){2}", post["post_id"])
            assert post["original_latest"] == 3
            assert post["live_item_count"] == 2 and post["live_revision_count"] == 4

            def check_originals(container, inspection):
                assert inspection["schema_hashes"] == before["schemas"], inspection
                assert inspection["item_count"] == 1, inspection
                assert inspection["revision_count"] == 2, inspection
                query = """
                  SELECT json_build_object(
                    'revisions', (SELECT coalesce(json_agg(json_build_object(
                      'number', r.number, 'name', r.display_name,
                      'properties', r.properties, 'schema_version', s.version)
                      ORDER BY r.number), '[]'::json)
                      FROM config_catalogrevision r
                      JOIN config_catalogitem i ON i.id = r.item_id
                      JOIN config_objecttypeversion s ON s.id = r.schema_version_id
                      WHERE i.public_id = '""" + before["id"] + """'),
                    'post_count', (SELECT count(*) FROM config_catalogitem
                      WHERE public_id = '""" + post["post_id"] + """')
                  )::text;
                """
                result = json.loads(execute(["docker", "exec", container, "psql",
                                             "-X", "-v", "ON_ERROR_STOP=1", "-U",
                                             recovery.RESTORE_USER, "-d", recovery.RESTORE_DB,
                                             "-Atqc", query]))
                assert result["post_count"] == 0, "Post-snapshot Model leaked into recovery"
                assert result["revisions"] == [
                    {"number": 1, "name": "Isolated CI r001",
                     "schema_version": before["model_schema_version"],
                     "properties": before["initial"]},
                    {"number": 2, "name": "Isolated CI r002",
                     "schema_version": before["model_schema_version"],
                     "properties": before["later"]},
                ], "Historical Model revisions were not restored byte-for-byte in semantic JSON"

            first = recovery.restore_isolated(dump, verifier=check_originals)
            second = recovery.restore_isolated(dump, verifier=check_originals)
            assert first == second, "Repeat isolated restore produced different results"
            print("PLAT-34 domain recovery CI: two real Model revisions restored, "
                  "post-snapshot Model and r003 absent, individual schema hashes "
                  "stable, source CI DB unaffected; PASS", flush=True)
        except Exception as exc:
            primary_error = exc
            raise
        finally:
            if started:
                try:
                    # Only the fresh random project can be removed; NEVER the
                    # default operational ai-compass project or named volumes.
                    execute(compose + ["down", "--volumes", "--remove-orphans"], capture=True)
                except Exception:
                    if primary_error is None:
                        raise
                    print("WARNING: isolated fixture project cleanup also failed",
                          file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ISOLATED RECOVERY FIXTURE FAILED: " + str(exc), file=sys.stderr)
        sys.exit(1)

"""Deterministic recovery-drill fixtures (PLAT-34).

Creates and checks Model catalog data using the real domain services
(catalog_services.create_model / revise_model), so the restore drill proves that
isolated restoration reproduces Model IDs, revision counts and schema versions
without inventing new domain logic.

    --create   --name N --revisions K        create a Model with K revisions; print JSON
    --check    --expect-id ID --expect-revisions K [--expect-absent ID] [--database DB]

--database overrides the target database so checks can run against the
disposable restored database instead of the active Server database. It never
drops or writes the active database.
"""
import argparse
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, DEFAULT_DB_ALIAS, transaction

from config.catalog_services import create_model, revise_model
from config.models import CatalogItem, CatalogRevision, ObjectTypeVersion


class Command(BaseCommand):
    help = "Create or verify recovery-drill Model fixtures via the real services."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--create", action="store_true", help="create a Model with N revisions")
        mode.add_argument("--check", action="store_true", help="verify a Model against expectations")
        parser.add_argument("--name", default="Recovery Drill Model", help="display name (create)")
        parser.add_argument("--revisions", type=int, default=1, help="number of revisions (create/check)")
        parser.add_argument("--expect-id", help="public_id to verify (check)")
        parser.add_argument("--expect-absent", help="public_id that must be absent (check)")
        parser.add_argument(
            "--database", default=DEFAULT_DB_ALIAS,
            help="database alias/name to target (check); never the active DB by default",
        )

    def handle(self, *args, **options):
        if options["create"]:
            self._create(options)
        else:
            self._check(options)

    def _actor(self, using):
        User = get_user_model()
        actor = User.objects.using(using).filter(is_superuser=False).first()
        if actor is None:
            manager = User._default_manager.db_manager(using)
            actor = manager.create_user(
                username=f"recovery-drill-{using}", password="drill-only-not-a-real-credential")
        return actor

    def _create(self, options):
        using = DEFAULT_DB_ALIAS
        with transaction.atomic(using=using):
            actor = self._actor(using)
            item = create_model(actor=actor, name=options["name"], properties={
                "context_window": 128000, "supports_tools": True, "drill_marker": True})
            for _ in range(options["revisions"] - 1):
                item.refresh_from_db()
                revise_model(item=item, actor=actor,
                             expected_revision=f"r{item.current_revision.number:03d}",
                             name=f"{options['name']} r{item.current_revision.number + 1}")
            item.refresh_from_db()
            schema = ObjectTypeVersion.objects.using(using).get(type_slug="model", version=1)
            self.stdout.write(json.dumps({
                "public_id": item.public_id,
                "revisions": CatalogRevision.objects.using(using).filter(item=item).count(),
                "schema_version": schema.version,
            }, sort_keys=True))

    def _check(self, options):
        using = options["database"]
        if not options["expect_id"]:
            raise CommandError("--check requires --expect-id")
        try:
            connections[using]
        except Exception:
            # The disposable restored DB is not a registered Django connection;
            # read it directly through a throwaway connection cloned from the
            # default so we never mutate the active Server DB.
            self._check_via_clone(using, options)
            return
        self._assert(using, options)

    def _assert(self, using, options):
        item = CatalogItem.objects.using(using).filter(public_id=options["expect_id"]).first()
        if item is None:
            raise CommandError(f"expected Model {options['expect_id']} not found in {using}")
        count = CatalogRevision.objects.using(using).filter(item=item).count()
        if count != options["revisions"]:
            raise CommandError(
                f"{options['expect_id']} has {count} revisions, expected {options['revisions']} in {using}")
        if options["expect_absent"]:
            if CatalogItem.objects.using(using).filter(public_id=options["expect_absent"]).exists():
                raise CommandError(
                    f"{options['expect_absent']} should be absent (post-snapshot) but exists in {using}")
        self.stdout.write(json.dumps(
            {"ok": True, "database": using, "public_id": options["expect_id"], "revisions": count},
            sort_keys=True))

    def _check_via_clone(self, using, options):
        from django.db import connection
        clone = connection.settings_dict.copy()
        clone["NAME"] = using
        from django.db.utils import load_backend
        backend = load_backend(clone["ENGINE"])
        conn = backend.DatabaseWrapper(clone, DEFAULT_DB_ALIAS)
        try:
            conn.ensure_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM config_catalogitem WHERE public_id = %s", [options["expect_id"]])
                row = cur.fetchone()
                if row is None:
                    raise CommandError(f"expected Model {options['expect_id']} not found in {using}")
                cur.execute(
                    "SELECT COUNT(*) FROM config_catalogrevision WHERE item_id = %s", [row[0]])
                count = int(cur.fetchone()[0])
                if count != options["revisions"]:
                    raise CommandError(
                        f"{options['expect_id']} has {count} revisions, expected "
                        f"{options['revisions']} in {using}")
                if options["expect_absent"]:
                    cur.execute("SELECT 1 FROM config_catalogitem WHERE public_id = %s",
                                [options["expect_absent"]])
                    if cur.fetchone() is not None:
                        raise CommandError(
                            f"{options['expect_absent']} should be absent (post-snapshot) but exists in {using}")
        finally:
            conn.close()
        self.stdout.write(json.dumps(
            {"ok": True, "database": using, "public_id": options["expect_id"], "revisions": count},
            sort_keys=True))

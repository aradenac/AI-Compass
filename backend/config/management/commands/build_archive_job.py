"""FUT-19: build one immutable archive artifact for a durable job (server-side).

Invoked as a separate process by the API so a large confidential archive is never
serialized inside an HTTP request. Emits a machine-readable reason token on
stderr and exits nonzero on any failure; never writes outside the private store.
"""
import os
import shutil
import tempfile

from django.core.management.base import BaseCommand, CommandError

from config.archive_job_services import (ArchiveJobError, record_artifact,
                                         store_root)
from config.archive_services import ArchiveError, build_native_export
from config.models import ArchiveJob


class Command(BaseCommand):
    help = "Build the immutable artifact for one queued archive job."

    def add_arguments(self, parser):
        parser.add_argument("public_id")

    def handle(self, *args, **options):
        try:
            job = ArchiveJob.objects.get(public_id=options["public_id"])
        except ArchiveJob.DoesNotExist as error:
            raise CommandError("unknown_job") from error
        if job.state != "running":
            raise CommandError("job_not_running")
        staging = None
        try:
            if job.kind == "native":
                build = build_native_export
            else:
                # A coordinated full-recovery artifact requires stopping the API
                # and sharing an isolated transfer with the operator CLI; it is
                # refused here rather than faked as an HTTP-produced job.
                raise ArchiveJobError("full_recovery_requires_operational_gate")
            output = build()
            try:
                output.seek(0)
                handle = tempfile.NamedTemporaryFile(
                    dir=store_root(), prefix="build-", suffix=".part", delete=False)
                staging = handle.name
                with handle:
                    shutil.copyfileobj(output, handle, length=1024 * 1024)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                output.close()
            record_artifact(job=job, path=staging)
        except (ArchiveJobError, ArchiveError) as error:
            self.stderr.write(str(error))
            raise CommandError(str(error)) from error
        except OSError:
            # Storage/integrity I/O problems are a fixed reason; an errno path is
            # never surfaced, so no filesystem layout leaks into job state.
            self.stderr.write("storage_unavailable")
            raise CommandError("storage_unavailable")
        finally:
            if staging:
                try:
                    os.unlink(staging)
                except FileNotFoundError:
                    pass

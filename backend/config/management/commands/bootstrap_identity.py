"""Create application roles and, optionally, one named non-superuser."""
from getpass import getpass
import sys

from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from config.identity import ROLES, ensure_roles


class Command(BaseCommand):
    help = "Install baseline roles and optionally create a role-scoped account."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Login to create (refuses overwrite).")
        parser.add_argument("--email", default="", help="Optional user email.")
        parser.add_argument("--role", action="append", choices=sorted(ROLES), default=[])
        parser.add_argument(
            "--password-stdin", action="store_true",
            help="Read password from stdin; no password is accepted as a CLI argument.",
        )

    def handle(self, *args, **options):
        if (options["role"] or options["password_stdin"]) and not options["username"]:
            raise CommandError("--role/--password-stdin require --username.")
        if options["username"] and not options["role"]:
            raise CommandError("Provide at least one explicit --role.")
        ensure_roles()
        username = options["username"]
        if not username:
            self.stdout.write(self.style.SUCCESS("Baseline roles and capabilities ready."))
            return
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise CommandError("Account already exists; refusing to overwrite roles or password.")
        if options["password_stdin"]:
            password = sys.stdin.readline().rstrip("\r\n")
        else:
            password = getpass("Password for new account: ")
            confirm = getpass("Confirm password: ")
            if password != confirm:
                raise CommandError("Passwords did not match.")
        if not password:
            raise CommandError("Password cannot be empty.")
        candidate = User(username=username, email=options["email"])
        try:
            password_validation.validate_password(password, candidate)
        except password_validation.ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        with transaction.atomic():
            if User.objects.select_for_update().filter(username=username).exists():
                raise CommandError("Account already exists.")
            candidate.set_password(password)
            candidate.is_staff = False
            candidate.is_superuser = False
            candidate.save()
            candidate.groups.add(*Group.objects.filter(name__in=options["role"]))
        self.stdout.write(
            self.style.SUCCESS(f"Created account {username!r} with roles: {', '.join(options['role'])}.")
        )

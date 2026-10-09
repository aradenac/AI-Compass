#!/usr/bin/env python3
"""Install a user-level systemd timer for PLAT-29 full daily backups.

Example: python3 scripts/install-backup-timer.py --destination /mnt/secure-backups --require-external
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def quote(value):
    text = str(value)
    if any(char in text for char in "\r\n\0%"):
        raise ValueError("Unsupported control/specifier in systemd unit value")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def create_units(destination, calendar, keep, require_external, db_only=False):
    if not destination.is_absolute() or not destination.is_dir():
        raise ValueError("Use an existing absolute destination directory")
    if keep < 1:
        raise ValueError("Must keep at least one verified backup")
    if not calendar.strip() or any(char in calendar for char in "\r\n\0%"):
        raise ValueError("Unsafe OnCalendar expression")
    python = quote(sys.executable)
    script = quote(ROOT / ("scripts/recovery.py" if db_only else "scripts/full_recovery.py"))
    target = quote(destination)
    external = "--require-external " if require_external else ""
    service = (
        "[Unit]\nDescription=AI Compass verified " + ("DB-only" if db_only else "DB plus evidence") + " backup and isolated restore drill\n"
        "ConditionPathIsDirectory=" + str(ROOT) + "\n\n"
        "[Service]\nType=oneshot\nWorkingDirectory=" + quote(ROOT) +
        "\nExecStart=" + python + " " + script + " --destination " + target + " " +
        external + "backup --keep " + str(keep) +
        "\nTimeoutStartSec=1200\nUMask=0077\n"
    )
    timer = (
        "[Unit]\nDescription=Schedule AI Compass verified backup\n\n"
        "[Timer]\nOnCalendar=" + calendar.strip() +
        "\nPersistent=true\nUnit=ai-compass-backup.service\n\n"
        "[Install]\nWantedBy=timers.target\n"
    )
    return service, timer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, help="Existing absolute backup directory")
    parser.add_argument("--require-external", action="store_true", help="Fail backup if destination is same filesystem")
    parser.add_argument("--calendar", default="daily", help="systemd OnCalendar expression (default: daily)")
    parser.add_argument("--keep", type=int, default=14, help="Number of last verified snapshots retained (default: 14)")
    parser.add_argument("--dry-run", action="store_true", help="Print units without writing or enabling")
    parser.add_argument("--db-only", action="store_true", help="Explicit legacy PLAT-34 DB-only timer; default protects evidence too")
    args = parser.parse_args()
    try:
        destination = Path(args.destination).expanduser()
        service, timer = create_units(destination, args.calendar, args.keep, args.require_external, db_only=args.db_only)
        if args.dry_run:
            print("----- ai-compass-backup.service -----\n" + service)
            print("----- ai-compass-backup.timer -----\n" + timer)
            return 0
        unit_dir = Path.home() / ".config/systemd/user"
        unit_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        for name, body in (("ai-compass-backup.service", service), ("ai-compass-backup.timer", timer)):
            path = unit_dir / name
            if path.is_symlink():
                raise ValueError("Refusing symlink systemd unit file: " + str(path))
            path.write_text(body, encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "ai-compass-backup.timer"], check=True)
        print("Enabled ai-compass-backup.timer. Check: systemctl --user list-timers ai-compass-backup.timer")
        print("Last run: journalctl --user -u ai-compass-backup.service -n 30")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print("Timer setup failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

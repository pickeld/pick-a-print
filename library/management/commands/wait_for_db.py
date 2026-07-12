import time

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Wait until the database is reachable"

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=60, help="Seconds to wait")

    def handle(self, *args, **options):
        timeout = options["timeout"]
        for attempt in range(1, timeout + 1):
            try:
                connection.ensure_connection()
                self.stdout.write(self.style.SUCCESS("Database is ready"))
                return
            except OperationalError:
                if attempt == timeout:
                    self.stderr.write(self.style.ERROR(f"Database not ready after {timeout}s"))
                    raise SystemExit(1)
                time.sleep(1)

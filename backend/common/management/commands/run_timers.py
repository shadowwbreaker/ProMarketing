from django.core.management.base import BaseCommand

from common.ops import run_all_timers


class Command(BaseCommand):
    help = "Run every periodic timer once (used where there is no celery beat, e.g. the Vercel beta)."

    def handle(self, *args, **opts):
        for name, res in run_all_timers().items():
            self.stdout.write(f"{name}: {res}")

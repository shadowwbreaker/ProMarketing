from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    help = "Mark a user's email as verified (local development / support)."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, email, **opts):
        n = User.objects.filter(email__iexact=email.strip()).update(is_email_verified=True)
        if not n:
            raise CommandError(f"User {email} not found")
        self.stdout.write(self.style.SUCCESS(f"{email}: email verified"))

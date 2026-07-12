from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token

User = get_user_model()


class Command(BaseCommand):
    help = "Create a dev user and print an API token"

    def add_arguments(self, parser):
        parser.add_argument("--username", default="dev")
        parser.add_argument("--password", default="devdevdev")
        parser.add_argument("--email", default="dev@localhost")

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username=options["username"],
            defaults={"email": options["email"]},
        )
        if created:
            user.set_password(options["password"])
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created user '{user.username}'"))
        else:
            self.stdout.write(f"User '{user.username}' already exists")

        token, _ = Token.objects.get_or_create(user=user)
        self.stdout.write(self.style.SUCCESS(f"API Token: {token.key}"))
        self.stdout.write(f"Use header: Authorization: Token {token.key}")

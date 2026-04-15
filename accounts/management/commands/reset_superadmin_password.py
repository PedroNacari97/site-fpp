"""Reseta (ou cria) o usuario superadmin com a senha informada."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Garante que o superadmin exista e redefine sua senha."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Nova senha do superadmin")
        parser.add_argument(
            "--email",
            default=None,
            help="Email do superadmin (default: settings.SUPERADMIN_EMAIL)",
        )
        parser.add_argument("--username", default="pedro", help="Username a usar se criar")

    def handle(self, *args, **options):
        User = get_user_model()
        email = (options["email"] or getattr(settings, "SUPERADMIN_EMAIL", "pedro@ncfly.com.br")).strip().lower()
        password = options["password"]
        username = options["username"]

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": username, "is_staff": True, "is_superuser": True},
        )
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"OK created={created} username={user.username} email={user.email} id={user.id}"
            )
        )

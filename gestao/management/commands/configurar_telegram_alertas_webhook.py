from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from gestao.services.telegram_alertas import telegram_set_webhook


class Command(BaseCommand):
    help = "Configura o webhook do bot do Telegram para o endpoint de alertas."

    def add_arguments(self, parser):
        parser.add_argument("base_url", type=str, help="Base publica do projeto, ex: https://ncfly.com.br")

    def handle(self, *args, **options):
        base_url = options["base_url"].rstrip("/")
        webhook_url = f"{base_url}{reverse('telegram_alertas_webhook')}"
        try:
            payload = telegram_set_webhook(webhook_url)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Webhook configurado com sucesso: {webhook_url}"))
        self.stdout.write(str(payload))

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from gestao.services.telegram_noticias import telegram_news_set_webhook


class Command(BaseCommand):
    help = "Configura o webhook do bot de noticias do Telegram."

    def add_arguments(self, parser):
        parser.add_argument(
            "base_url",
            nargs="?",
            help="Base publica do site, por exemplo https://ncfly.com.br",
        )

    def handle(self, *args, **options):
        base_url = (options.get("base_url") or getattr(settings, "SITE_BASE_URL", "")).strip().rstrip("/")
        if not base_url:
            raise CommandError("Informe a base publica do site ou defina SITE_BASE_URL.")

        webhook_url = f"{base_url}/integracoes/telegram/noticias/webhook/"
        try:
            payload = telegram_news_set_webhook(webhook_url)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Webhook de noticias configurado com sucesso: {webhook_url}"))
        self.stdout.write(str(payload))

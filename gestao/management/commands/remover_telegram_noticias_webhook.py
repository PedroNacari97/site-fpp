from django.core.management.base import BaseCommand, CommandError

from gestao.services.telegram_noticias import telegram_news_delete_webhook


class Command(BaseCommand):
    help = "Remove o webhook do bot de noticias do Telegram para permitir testes locais com polling."

    def add_arguments(self, parser):
        parser.add_argument(
            "--drop-pending-updates",
            action="store_true",
            help="Descarta updates pendentes no Telegram ao remover o webhook.",
        )

    def handle(self, *args, **options):
        try:
            payload = telegram_news_delete_webhook(
                drop_pending_updates=options["drop_pending_updates"]
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Webhook do Telegram de noticias removido com sucesso."))
        self.stdout.write(str(payload))

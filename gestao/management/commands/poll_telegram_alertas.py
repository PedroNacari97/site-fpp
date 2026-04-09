from django.core.management.base import BaseCommand, CommandError

from gestao.services.telegram_alertas import process_telegram_alert_update, telegram_get_updates


class Command(BaseCommand):
    help = "Busca updates do bot do Telegram e cadastra alertas automaticamente."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20, help="Quantidade maxima de updates por execucao.")
        parser.add_argument("--timeout", type=int, default=0, help="Long polling em segundos para o getUpdates.")

    def handle(self, *args, **options):
        limit = options["limit"]
        timeout = options["timeout"]
        try:
            updates = telegram_get_updates(limit=limit, timeout=timeout)
        except Exception as exc:
            message = str(exc)
            if "409 Client Error: Conflict" in message or "Conflict for url" in message:
                raise CommandError(
                    "O bot está com webhook ativo no Telegram. "
                    "Para testar local com polling, rode antes: "
                    "`py manage.py remover_telegram_alertas_webhook`"
                ) from exc
            raise CommandError(message) from exc

        counters = {
            "created": 0,
            "duplicate_update": 0,
            "ignored_chat": 0,
            "ignored_empty": 0,
            "ignored_duplicate_message": 0,
            "parse_error": 0,
        }

        for update in updates:
            event, outcome = process_telegram_alert_update(update)
            counters[outcome] = counters.get(outcome, 0) + 1
            self.stdout.write(f"update={event.update_id} outcome={outcome} alerta={event.alerta_id or '-'}")

        self.stdout.write(
            self.style.SUCCESS(
                "Polling concluido. "
                f"novos={counters['created']} "
                f"duplicados_update={counters['duplicate_update']} "
                f"duplicados_mensagem={counters['ignored_duplicate_message']} "
                f"ignorados_chat={counters['ignored_chat']} "
                f"vazios={counters['ignored_empty']} "
                f"erros_parse={counters['parse_error']}"
            )
        )

from django.core.management.base import BaseCommand, CommandError

from gestao.services.telegram_noticias import (
    process_telegram_news_update,
    telegram_news_get_updates,
    telegram_news_send_message,
)


class Command(BaseCommand):
    help = "Busca updates do bot de noticias do Telegram e processa atualizar/link/texto."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20, help="Quantidade maxima de updates por execucao.")
        parser.add_argument("--timeout", type=int, default=0, help="Long polling em segundos para o getUpdates.")
        parser.add_argument(
            "--no-reply",
            action="store_true",
            help="Nao envia mensagem de retorno no Telegram apos processar.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        timeout = options["timeout"]
        no_reply = options["no_reply"]
        try:
            updates = telegram_news_get_updates(limit=limit, timeout=timeout)
        except Exception as exc:
            message = str(exc)
            if "409 Client Error: Conflict" in message or "Conflict for url" in message:
                raise CommandError(
                    "O bot de noticias esta com webhook ativo no Telegram. "
                    "Para testar local com polling, rode antes: "
                    "`py manage.py remover_telegram_noticias_webhook`"
                ) from exc
            raise CommandError(message) from exc

        counters = {
            "sync_batch": 0,
            "duplicate_update": 0,
            "ignored_chat": 0,
            "ignored_empty": 0,
            "ignored_duplicate_message": 0,
            "ignored_unknown_format": 0,
            "processing_error": 0,
        }

        for update in updates:
            event, outcome, meta = process_telegram_news_update(update)
            counters[outcome] = counters.get(outcome, 0) + 1
            self.stdout.write(f"update={event.update_id} outcome={outcome} noticia={event.noticia_id or '-'}")
            if meta.get("message"):
                self.stdout.write(f"mensagem={meta['message']}")

            if no_reply or not event.chat_id:
                continue

            message = meta.get("message")
            if not message:
                if outcome == "ignored_unknown_format":
                    message = "Formato nao suportado. Envie 'atualizar 10', um link ou um texto promocional."
                elif outcome == "ignored_chat":
                    message = "Esse chat nao esta autorizado para o bot de noticias."
                elif outcome == "ignored_duplicate_message":
                    message = "Essa mensagem ja foi processada antes."
                elif outcome == "duplicate_update":
                    message = None
                elif outcome == "ignored_empty":
                    message = "Nao encontrei texto util para processar."
                elif outcome == "processing_error":
                    message = "Ocorreu um erro ao processar sua solicitacao."

            if message:
                try:
                    telegram_news_send_message(event.chat_id, message)
                except Exception as exc:
                    self.stderr.write(f"Falha ao responder no Telegram para o update {event.update_id}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                "Polling noticias concluido. "
                f"batch={counters['sync_batch']} "
                f"duplicados_update={counters['duplicate_update']} "
                f"duplicados_mensagem={counters['ignored_duplicate_message']} "
                f"ignorados_chat={counters['ignored_chat']} "
                f"ignorados_formato={counters['ignored_unknown_format']} "
                f"vazios={counters['ignored_empty']} "
                f"erros={counters['processing_error']}"
            )
        )

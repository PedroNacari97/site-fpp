import os

from django.core.management.base import BaseCommand, CommandError

from gestao.services.telegram_artigos import (
    process_telegram_artigos_update,
    telegram_artigos_get_updates,
    telegram_artigos_send_message,
)


class Command(BaseCommand):
    help = "Busca updates do bot de artigos do Telegram e processa com IA."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10, help="Quantidade máxima de updates por execução.")
        parser.add_argument("--timeout", type=int, default=0, help="Long polling em segundos.")
        parser.add_argument("--no-reply", action="store_true", help="Não envia resposta no Telegram após processar.")
        parser.add_argument("--offset", type=int, default=None, help="Update ID de offset para getUpdates.")

    def handle(self, *args, **options):
        if not os.environ.get("TELEGRAM_ARTIGOS_BOT_TOKEN"):
            raise CommandError("TELEGRAM_ARTIGOS_BOT_TOKEN não configurado no .env")

        limit = options["limit"]
        timeout = options["timeout"]
        no_reply = options["no_reply"]
        offset = options["offset"]

        self.stdout.write("Buscando updates do bot de artigos...")

        try:
            updates = telegram_artigos_get_updates(limit=limit, timeout=timeout, offset=offset)
        except Exception as exc:
            message = str(exc)
            if "409" in message or "Conflict" in message:
                raise CommandError(
                    "O bot de artigos está com webhook ativo no Telegram. "
                    "Para testar local com polling, remova o webhook primeiro."
                ) from exc
            raise CommandError(message) from exc

        if not updates:
            self.stdout.write("Nenhum update pendente.")
            return

        self.stdout.write(f"{len(updates)} update(s) encontrado(s).")

        counters = {"published": 0, "text_too_short": 0, "ignored_empty": 0, "processing_error": 0}

        for update in updates:
            update_id, outcome, meta = process_telegram_artigos_update(update)
            counters[outcome] = counters.get(outcome, 0) + 1

            noticia_id = meta.get("noticia_id", "-")
            self.stdout.write(f"  update={update_id} outcome={outcome} noticia={noticia_id}")

            if not no_reply and meta.get("chat_id") and meta.get("message"):
                try:
                    telegram_artigos_send_message(meta["chat_id"], meta["message"])
                except Exception as exc:
                    self.stderr.write(f"  Falha ao responder no Telegram (update {update_id}): {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Concluído — publicados={counters['published']} "
                f"curtos={counters['text_too_short']} "
                f"vazios={counters['ignored_empty']} "
                f"erros={counters['processing_error']}"
            )
        )

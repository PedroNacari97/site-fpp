"""Polling do bot publico de consulta de status de voo.

Uso local:

    python manage.py poll_telegram_status_voo --loop

Em producao (Railway), preferir webhook (a implementar) — para evitar manter
um worker em loop infinito.
"""
import time

from django.core.management.base import BaseCommand, CommandError

from gestao.services.telegram_status_voo import (
    delete_webhook,
    get_updates,
    processar_lote,
)


class Command(BaseCommand):
    help = "Polling do bot publico de consulta de status de voo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Quantidade maxima de updates por request.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=25,
            help="Long polling em segundos (25 é o sweet spot do Telegram).",
        )
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Roda em loop ate Ctrl+C. Sem essa flag faz uma unica chamada.",
        )
        parser.add_argument(
            "--reset-webhook",
            action="store_true",
            help="Remove webhook antes de comecar (necessario p/ polling).",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        timeout = options["timeout"]
        loop = options["loop"]
        if options.get("reset_webhook"):
            try:
                delete_webhook()
                self.stdout.write(self.style.SUCCESS("Webhook removido."))
            except Exception as exc:
                raise CommandError(f"Falha ao remover webhook: {exc}") from exc

        self.stdout.write(
            self.style.NOTICE(
                f"Polling status-voo (loop={loop} timeout={timeout}s limit={limit})"
            )
        )

        try:
            while True:
                try:
                    updates = get_updates(limit=limit, timeout=timeout)
                except Exception as exc:
                    msg = str(exc)
                    if "409" in msg or "Conflict" in msg:
                        raise CommandError(
                            "Webhook ativo no Telegram. Rode novamente com "
                            "--reset-webhook."
                        ) from exc
                    self.stderr.write(f"Erro no getUpdates: {exc}")
                    if not loop:
                        raise
                    time.sleep(5)
                    continue

                if updates:
                    contadores = processar_lote(updates)
                    self.stdout.write(
                        f"updates={len(updates)} acoes={contadores}"
                    )

                if not loop:
                    break
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nInterrompido pelo usuario."))

from django.core.management.base import BaseCommand

from portal.services.alert_email_broadcasts import send_pending_alert_digest


class Command(BaseCommand):
    help = "Envia o digest pendente de alertas por e-mail para quem se cadastrou na lista de alertas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-items",
            type=int,
            default=None,
            help="Quantidade maxima de itens pendentes para incluir neste envio.",
        )
        parser.add_argument(
            "--remaining-slots",
            type=int,
            default=None,
            help="Quantidade de janelas restantes no dia, incluindo a execucao atual.",
        )

    def handle(self, *args, **options):
        result = send_pending_alert_digest(
            max_items=options.get("max_items"),
            remaining_slots=options.get("remaining_slots"),
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Digest de alertas processado. "
                f"itens={result['items']} destinatarios={result['recipients']} enviados={result['emails_sent']}"
            )
        )

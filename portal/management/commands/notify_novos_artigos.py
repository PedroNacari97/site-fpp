from django.core.management.base import BaseCommand

from portal.services.artigo_notifications import dispatch_pending_artigo_notifications


class Command(BaseCommand):
    help = (
        "Envia notificacao de novos artigos (ArtigoEstudo publicados) para "
        "PortalUsers com OptInArtigoNovo ativo. Marca artigo.notificado_em "
        "apos o envio."
    )

    def handle(self, *args, **options):
        result = dispatch_pending_artigo_notifications()
        self.stdout.write(
            self.style.SUCCESS(
                "Notificacao de novos artigos processada. "
                f"artigos={result['artigos']} destinatarios={result['destinatarios']} "
                f"enviados={result['enviados']}"
            )
        )

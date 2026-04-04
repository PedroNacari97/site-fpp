from django.core.management.base import BaseCommand

from gestao.models import ContaFidelidade
from gestao.services.conta_clube import sync_club_movements_for_queryset


class Command(BaseCommand):
    help = "Sincroniza as recorrencias de clube das contas fidelidade e gera movimentacoes automaticas."

    def handle(self, *args, **options):
        contas = (
            ContaFidelidade.objects.exclude(clube_periodicidade="nenhum")
            .exclude(data_inicio_clube__isnull=True)
            .select_related("programa", "cliente__usuario", "conta_administrada")
        )
        total = sync_club_movements_for_queryset(contas)
        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronizacao concluida. Movimentacoes de clube criadas ou atualizadas: {total}"
            )
        )

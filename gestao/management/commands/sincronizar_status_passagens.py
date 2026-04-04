from django.core.management.base import BaseCommand

from gestao.models import AcompanhamentoPassagem, EmissaoPassagem
from gestao.services.acompanhamento_passagem import (
    ensure_acompanhamento_passagem,
    sync_acompanhamento_passagem,
)


class Command(BaseCommand):
    help = "Sincroniza os acompanhamentos de passagem ativos."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--emissao-id", type=int, default=None)

    def handle(self, *args, **options):
        limit = options["limit"]
        emissao_id = options["emissao_id"]

        if emissao_id:
            emissoes = EmissaoPassagem.objects.filter(id=emissao_id)
        else:
            emissoes = EmissaoPassagem.objects.order_by("-criado_em")[:limit]

        total = 0
        sucesso = 0
        falhas = 0
        for emissao in emissoes:
            acompanhamento = ensure_acompanhamento_passagem(emissao)
            if not acompanhamento.ativo:
                continue
            total += 1
            result = sync_acompanhamento_passagem(acompanhamento)
            if result.success:
                sucesso += 1
            else:
                falhas += 1
            self.stdout.write(
                f"Emissao #{emissao.id}: {result.message}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronizacao concluida. Processados={total}, sucesso={sucesso}, falhas={falhas}"
            )
        )

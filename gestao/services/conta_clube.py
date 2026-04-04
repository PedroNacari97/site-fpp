from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.utils import timezone

from gestao.models import ContaFidelidade, Movimentacao


PERIODICIDADE_MESES = {
    "mensal": 1,
    "trimestral": 3,
    "semestral": 6,
    "anual": 12,
}


def _add_months(base_date: date, months: int) -> date:
    total_months = (base_date.year * 12 + (base_date.month - 1)) + months
    year = total_months // 12
    month = total_months % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _periodicidade_label(conta: ContaFidelidade) -> str:
    return dict(ContaFidelidade.PERIODICIDADE_CLUBE).get(
        conta.clube_periodicidade, conta.clube_periodicidade
    )


def should_sync_club(conta: ContaFidelidade) -> bool:
    return bool(
        conta
        and conta.clube_periodicidade in PERIODICIDADE_MESES
        and conta.data_inicio_clube
        and ((conta.pontos_clube_mes or 0) > 0 or Decimal(conta.valor_assinatura_clube or 0) > 0)
    )


def sync_club_movements_for_account(
    conta: ContaFidelidade, *, up_to: date | None = None
) -> int:
    conta_base = conta.conta_saldo() if hasattr(conta, "conta_saldo") else conta
    sync_until = up_to or timezone.localdate()

    if getattr(conta_base, "_club_sync_until", None) == sync_until:
        return 0

    if not should_sync_club(conta_base):
        conta_base._club_sync_until = sync_until
        return 0

    periodicidade_meses = PERIODICIDADE_MESES[conta_base.clube_periodicidade]
    recorrencia = conta_base.data_inicio_clube
    pontos = int(conta_base.pontos_clube_mes or 0)
    valor = Decimal(conta_base.valor_assinatura_clube or 0)
    descricao_base = _periodicidade_label(conta_base)
    processed = 0

    while recorrencia and recorrencia <= sync_until:
        chave_origem = f"clube:{recorrencia.isoformat()}"
        Movimentacao.objects.update_or_create(
            conta=conta_base,
            chave_origem=chave_origem,
            defaults={
                "data": recorrencia,
                "pontos": pontos,
                "valor_pago": valor,
                "descricao": f"Clube {descricao_base} - {recorrencia.strftime('%m/%Y')}",
                "tipo": Movimentacao.TIPO_CLUBE,
            },
        )
        processed += 1
        recorrencia = _add_months(recorrencia, periodicidade_meses)

    conta_base._club_sync_until = sync_until
    return processed


def sync_club_movements_for_queryset(contas) -> int:
    total = 0
    processed_ids = set()
    for conta in contas:
        conta_base = conta.conta_saldo() if hasattr(conta, "conta_saldo") else conta
        if conta_base.pk in processed_ids:
            continue
        total += sync_club_movements_for_account(conta_base)
        processed_ids.add(conta_base.pk)
    return total

"""Serviços para cálculo financeiro de emissões e movimentações de pontos."""

from decimal import Decimal

from django.utils import timezone

from gestao.models import ContaFidelidade, EmissaoPassagem, Movimentacao


def calcular_valor_referencia_pontos(pontos_utilizados: int, valor_medio_milheiro: float) -> Decimal:
    """Retorna o custo real dos pontos usados usando o valor médio do cliente."""

    pontos = Decimal(pontos_utilizados or 0)
    valor_medio = Decimal(valor_medio_milheiro) if valor_medio_milheiro is not None else Decimal("0")
    return (pontos / Decimal("1000")) * valor_medio


def calcular_economia(emissao: EmissaoPassagem, valor_referencia_pontos: Decimal) -> Decimal:
    """Calcula a economia considerando dinheiro + custo real dos pontos."""

    valor_referencia = Decimal(emissao.valor_referencia or 0)
    valor_pago = Decimal(emissao.valor_pago or 0)
    return valor_referencia - (valor_pago + valor_referencia_pontos)


def registrar_movimentacao_pontos(
    conta: ContaFidelidade,
    emissao: EmissaoPassagem,
    pontos_utilizados: int,
    valor_referencia_pontos: Decimal,
):
    """Cria ou atualiza a movimentação de saída de pontos da emissão."""

    conta_base = conta.conta_saldo()
    descricao = f"Emissão #{emissao.id} - uso de pontos"
    if not pontos_utilizados:
        Movimentacao.objects.filter(conta=conta_base, descricao=descricao).delete()
        return

    Movimentacao.objects.update_or_create(
        conta=conta_base,
        descricao=descricao,
        defaults={
            "data": getattr(emissao, "data_ida", None).date() if getattr(emissao, "data_ida", None) else timezone.now().date(),
            "pontos": -int(pontos_utilizados),
            "valor_pago": -valor_referencia_pontos,
        },
    )

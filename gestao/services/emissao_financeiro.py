"""Serviços para cálculo financeiro de emissões e movimentações de pontos."""

from decimal import Decimal

from django.utils import timezone

from gestao.models import ContaFidelidade, EmissaoPassagem, Movimentacao


def calcular_valor_referencia_pontos(pontos_utilizados: int, valor_medio_milheiro: float) -> Decimal:
    """Retorna o custo real dos pontos usados usando o valor médio do cliente."""

    pontos = Decimal(pontos_utilizados or 0)
    valor_medio = Decimal(valor_medio_milheiro) if valor_medio_milheiro is not None else Decimal("0")
    return (pontos / Decimal("1000")) * valor_medio


def calcular_custo_milhas(pontos_utilizados: int, valor_milheiro: Decimal | float) -> Decimal:
    """Retorna o custo das milhas baseado no valor do milheiro da emissão."""

    pontos = Decimal(pontos_utilizados or 0)
    valor = Decimal(valor_milheiro or 0)
    return (pontos / Decimal("1000")) * valor


def calcular_custo_total_emissao(
    emissao: EmissaoPassagem, valor_milheiro: Decimal | float, incluir_taxas: bool = True
) -> Decimal:
    """Calcula o custo total da emissão, com opção de incluir taxas."""

    custo_milhas = calcular_custo_milhas(emissao.pontos_utilizados or 0, valor_milheiro)
    if incluir_taxas:
        custo_milhas += Decimal(emissao.valor_taxas or 0)
    return custo_milhas


def calcular_lucro_emissao(emissao: EmissaoPassagem, custo_base: Decimal | float) -> Decimal:
    """Calcula o lucro da emissão considerando o custo base informado."""

    valor_total = getattr(emissao, "valor_total_final", None)
    valor_final_cliente = emissao.valor_venda_final
    if valor_total not in (None, ""):
        return Decimal(valor_total or 0) - Decimal(custo_base or 0)
    if valor_final_cliente in (None, ""):
        return Decimal("0")
    return Decimal(valor_final_cliente or 0) - Decimal(custo_base or 0)


def calcular_economia(emissao: EmissaoPassagem, custo_total: Decimal | float) -> Decimal:
    """Calcula a economia obtida seguindo as regras de valor final e custo total."""

    if emissao.valor_venda_final not in (None, ""):
        return Decimal(emissao.valor_venda_final or 0) - Decimal(emissao.valor_referencia or 0)
    return Decimal("0")


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

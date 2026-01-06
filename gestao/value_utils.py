"""Utilidades para cálculos de valor de referência de programas."""

from decimal import Decimal
from typing import Dict

from gestao.models import ValorMilheiro, ProgramaFidelidade


def _normalize_program_name(name: str) -> str:
    """Normalize program names for consistent lookups."""
    return (name or "").strip().lower()


def build_valor_milheiro_map() -> Dict[str, Decimal]:
    """Retorna um dicionário ``nome_programa -> valor_mercado``.

    O nome é normalizado para minúsculas para facilitar o *lookup* sem
    depender de capitalização exata.
    """

    return {
        _normalize_program_name(vm.programa_nome): Decimal(vm.valor_mercado)
        for vm in ValorMilheiro.objects.all()
        if _normalize_program_name(vm.programa_nome)
    }


def get_valor_referencia_from_map(
    programa: ProgramaFidelidade, valores_map: Dict[str, Decimal]
) -> Decimal:
    """Obtém o valor de referência (mercado) para o programa informado.

    IMPORTANTE: Para programas VINCULADOS, usa o valor específico do programa vinculado,
    não do programa base. Isso permite que AZUL e AZUL PELO MUNDO tenham valores diferentes.

    A busca considera:
    1. O valor de mercado do próprio programa (se existir)
    2. O valor de mercado do programa base (se for vinculado e existir)
    3. O preco_medio_milheiro configurado do programa
    4. O preco_medio_milheiro do programa base (se for vinculado)
    5. Retorna Decimal('0') se nenhum valor for encontrado
    """

    if not programa:
        return Decimal("0")

    # PASSO 1: Tentar encontrar valor de mercado do programa atual
    valor = valores_map.get(_normalize_program_name(programa.nome))
    if valor is not None:
        return valor

    # PASSO 2: Se for vinculado, tentar valor de mercado do programa base
    if programa.is_vinculado and programa.programa_base:
        valor = valores_map.get(_normalize_program_name(programa.programa_base.nome))
        if valor is not None:
            return valor

    # PASSO 3: Usar o preco_medio_milheiro configurado do PRÓPRIO PROGRAMA
    # (não do base, para que AZUL e AZUL PELO MUNDO tenham valores diferentes)
    if getattr(programa, "preco_medio_milheiro", None):
        return Decimal(programa.preco_medio_milheiro)

    # PASSO 4: Se for vinculado e não tiver valor próprio, usar o do programa base como fallback
    if programa.is_vinculado and programa.programa_base:
        base_preco = getattr(programa.programa_base, "preco_medio_milheiro", None)
        if base_preco:
            return Decimal(base_preco)

    # PASSO 5: Nenhum valor encontrado
    return Decimal("0")
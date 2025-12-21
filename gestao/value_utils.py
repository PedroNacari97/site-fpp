"""Utilidades para cálculos de valor de referência de programas."""

from decimal import Decimal
from typing import Dict

from gestao.models import ValorMilheiro, ProgramaFidelidade


def build_valor_milheiro_map() -> Dict[str, Decimal]:
    """Retorna um dicionário ``nome_programa -> valor_mercado``.

    O nome é normalizado para minúsculas para facilitar o *lookup* sem
    depender de capitalização exata.
    """

    return {
        vm.programa_nome.lower(): Decimal(vm.valor_mercado)
        for vm in ValorMilheiro.objects.all()
    }


def get_valor_referencia_from_map(
    programa: ProgramaFidelidade, valores_map: Dict[str, Decimal]
) -> Decimal:
    """Obtém o valor de referência (mercado) para o programa informado.

    A busca considera o próprio programa e, quando houver, o programa base
    vinculado. Caso não exista valor cadastrado, retorna ``Decimal('0')``.
    """

    if not programa:
        return Decimal("0")

    candidatos = [programa.nome]
    if programa.is_vinculado and programa.programa_base:
        candidatos.insert(0, programa.programa_base.nome)

    for nome in candidatos:
        valor = valores_map.get(nome.lower())
        if valor is not None:
            return valor

    return Decimal("0")

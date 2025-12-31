"""Serviços para validação de limite de CPFs por programa."""

from typing import Iterable, Set, Tuple

from django.core.exceptions import ValidationError

from gestao.models import Passageiro, ProgramaFidelidade
from gestao.utils import normalize_cpf


def _build_existing_cpfs(
    *,
    programa_id: int,
    exclude_emissao_id: int | None = None,
) -> Set[str]:
    filtros = {"emissao__programa_id": programa_id}

    qs = Passageiro.objects.filter(**filtros)
    if exclude_emissao_id:
        qs = qs.exclude(emissao_id=exclude_emissao_id)

    cpfs = set()
    for cpf in qs.values_list("cpf", flat=True):
        normalized = normalize_cpf(cpf)
        if normalized:
            cpfs.add(normalized)
    return cpfs


def _normalize_cpfs(cpfs: Iterable[str]) -> Set[str]:
    normalized_cpfs = set()
    for cpf in cpfs:
        normalized = normalize_cpf(cpf)
        if normalized:
            normalized_cpfs.add(normalized)
    return normalized_cpfs


def _get_limite_programa(programa: ProgramaFidelidade) -> int | None:
    return programa.quantidade_cpfs_disponiveis


def validar_limite_cpfs(
    conta_ou_programa, cpfs: Iterable[str], emissao_id: int | None = None
) -> Tuple[int, int | None]:
    """Valida o consumo de CPFs e retorna (cpfs_novos, cpfs_disponiveis)."""

    programa = (
        conta_ou_programa.programa
        if hasattr(conta_ou_programa, "programa")
        else conta_ou_programa
    )
    limite = _get_limite_programa(programa)
    if limite is None:
        return 0, None

    cpfs_existentes = _build_existing_cpfs(
        programa_id=programa.id,
        exclude_emissao_id=emissao_id,
    )
    cpfs_na_emissao = _normalize_cpfs(cpfs)
    cpfs_novos = cpfs_na_emissao - cpfs_existentes
    cpfs_disponiveis = max(limite - len(cpfs_existentes), 0)

    if len(cpfs_novos) > cpfs_disponiveis:
        raise ValidationError(
            f"Limite de CPFs excedido. Esta emissão adiciona {len(cpfs_novos)} CPF(s) novos, "
            f"mas restam apenas {cpfs_disponiveis} disponível(is) no programa."
        )

    return len(cpfs_novos), cpfs_disponiveis

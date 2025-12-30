"""Serviços para validação de limite de CPFs por programa."""

from typing import Iterable, Set, Tuple

from django.core.exceptions import ValidationError

from gestao.models import Passageiro
from gestao.utils import normalize_cpf


def _build_existing_cpfs(
    *,
    programa_id: int,
    cliente_id: int | None = None,
    conta_administrada_id: int | None = None,
    exclude_emissao_id: int | None = None,
) -> Set[str]:
    filtros = {"emissao__programa_id": programa_id}
    if cliente_id:
        filtros["emissao__cliente_id"] = cliente_id
    if conta_administrada_id:
        filtros["emissao__conta_administrada_id"] = conta_administrada_id

    qs = Passageiro.objects.filter(**filtros)
    if exclude_emissao_id:
        qs = qs.exclude(emissao_id=exclude_emissao_id)

    cpfs = set()
    for documento in qs.values_list("documento", flat=True):
        normalized = normalize_cpf(documento)
        if normalized:
            cpfs.add(normalized)
    return cpfs


def _normalize_documentos(documentos: Iterable[str]) -> Set[str]:
    cpfs = set()
    for doc in documentos:
        normalized = normalize_cpf(doc)
        if normalized:
            cpfs.add(normalized)
    return cpfs


def validar_limite_cpfs(conta, documentos: Iterable[str], emissao_id: int | None = None) -> Tuple[int, int | None]:
    """Valida o consumo de CPFs e retorna (cpfs_novos, cpfs_disponiveis)."""

    limite = conta.quantidade_cpfs_disponiveis
    if limite is None:
        return 0, None

    cpfs_existentes = _build_existing_cpfs(
        programa_id=conta.programa_id,
        cliente_id=conta.cliente_id,
        conta_administrada_id=conta.conta_administrada_id,
        exclude_emissao_id=emissao_id,
    )
    cpfs_na_emissao = _normalize_documentos(documentos)
    cpfs_novos = cpfs_na_emissao - cpfs_existentes
    cpfs_disponiveis = max(limite - len(cpfs_existentes), 0)

    if len(cpfs_novos) > cpfs_disponiveis:
        raise ValidationError(
            f"Limite de CPFs excedido. Esta emissão adiciona {len(cpfs_novos)} CPF(s) novos, "
            f"mas restam apenas {cpfs_disponiveis} disponível(is) no programa."
        )

    return len(cpfs_novos), cpfs_disponiveis

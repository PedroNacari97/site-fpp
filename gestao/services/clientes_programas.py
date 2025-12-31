"""Serviços para mapear programas vinculados a clientes."""

from typing import Dict, List
from django.db.models import Count, Q

from gestao.models import ContaFidelidade, EmissaoPassagem, Passageiro, ProgramaFidelidade
from gestao.utils import normalize_cpf

Key = int


def _build_cpfs_map(empresa_id=None) -> Dict[Key, int]:
    """Retorna um mapa programa_id -> CPFs distintos usados."""

    filtros = Q(emissao__programa__isnull=False)
    if empresa_id:
        filtros &= (
            Q(emissao__cliente__empresa_id=empresa_id)
            | Q(emissao__conta_administrada__empresa_id=empresa_id)
        )
    cpfs_qs = (
        Passageiro.objects.filter(filtros)
        .values("emissao__programa_id")
        .annotate(qtd=Count("cpf", distinct=True))
    )
    return {row["emissao__programa_id"]: row["qtd"] for row in cpfs_qs}


def _build_cpfs_sets_map(empresa_id=None, exclude_emissao_id=None) -> Dict[Key, set]:
    """Retorna um mapa programa_id -> conjunto de CPFs normalizados."""

    filtros = Q(emissao__programa__isnull=False)
    if empresa_id:
        filtros &= (
            Q(emissao__cliente__empresa_id=empresa_id)
            | Q(emissao__conta_administrada__empresa_id=empresa_id)
        )
    cpfs_qs = Passageiro.objects.filter(filtros)
    if exclude_emissao_id:
        cpfs_qs = cpfs_qs.exclude(emissao_id=exclude_emissao_id)
    cpfs_map: Dict[Key, set] = {}
    for row in cpfs_qs.values("emissao__programa_id", "cpf"):
        key = row["emissao__programa_id"]
        normalized = normalize_cpf(row["cpf"])
        if not normalized:
            continue
        cpfs_map.setdefault(key, set()).add(normalized)
    return cpfs_map


def _get_limite_cpfs(conta: ContaFidelidade) -> int | None:
    return (
        conta.programa.quantidade_cpfs_disponiveis
        if conta.programa.quantidade_cpfs_disponiveis is not None
        else conta.quantidade_cpfs_disponiveis
    )


def build_clientes_programas_map(
    instance=None, empresa_id=None, exclude_emissao_id=None
) -> Dict[int, List[dict]]:
    """Retorna um mapa ``cliente_id -> lista de programas e saldos``."""

    contas = ContaFidelidade.objects.filter(
        cliente__perfil="cliente",
        cliente__ativo=True,
        conta_administrada__isnull=True,
    ).select_related("programa", "cliente__usuario")
    if empresa_id:
        contas = contas.filter(cliente__empresa_id=empresa_id)
    if instance and exclude_emissao_id is None and isinstance(instance, EmissaoPassagem):
        exclude_emissao_id = getattr(instance, "id", None)
    cpfs_sets_map = _build_cpfs_sets_map(empresa_id, exclude_emissao_id)
    data = {}
    for conta in contas:
        key = conta.programa_id
        cpfs_usados_list = sorted(cpfs_sets_map.get(key, set()))
        cpfs_usados = len(cpfs_usados_list)
        limite_cpfs = _get_limite_cpfs(conta)
        cpfs_disponiveis = None if limite_cpfs is None else max(limite_cpfs - cpfs_usados, 0)
        data.setdefault(conta.cliente_id, [])
        data[conta.cliente_id].append(
            {
                "id": conta.programa_id,
                "nome": conta.programa.nome,
                "saldo": conta.saldo_pontos,
                "valor_medio": float(conta.valor_medio_por_mil or 0),
                "cpfs_disponiveis": cpfs_disponiveis,
                "cpfs_total": limite_cpfs,
                "cpfs_usados": cpfs_usados,
                "cpfs_usados_list": cpfs_usados_list,
            }
        )

    if instance and getattr(instance, "programa_id", None) and getattr(instance, "cliente_id", None):
        if instance.cliente_id not in data:
            data[instance.cliente_id] = []
        if not any(p["id"] == instance.programa_id for p in data[instance.cliente_id]):
            data[instance.cliente_id].append(
                {
                    "id": instance.programa_id,
                    "nome": str(instance.programa),
                    "saldo": 0,
                    "valor_medio": 0,
                    "cpfs_disponiveis": instance.programa.quantidade_cpfs_disponiveis,
                    "cpfs_total": instance.programa.quantidade_cpfs_disponiveis,
                    "cpfs_usados": len(cpfs_sets_map.get(instance.programa_id, set())),
                    "cpfs_usados_list": sorted(cpfs_sets_map.get(instance.programa_id, set())),
                }
            )
    return data


def build_contas_administradas_programas_map(
    empresa_id=None, instance=None, exclude_emissao_id=None
) -> Dict[int, List[dict]]:
    """Retorna um mapa ``conta_administrada_id -> lista de programas e saldos``."""

    contas = ContaFidelidade.objects.filter(
        conta_administrada__isnull=False,
        conta_administrada__ativo=True,
    ).select_related("programa", "conta_administrada")
    if empresa_id:
        contas = contas.filter(conta_administrada__empresa_id=empresa_id)

    if instance and exclude_emissao_id is None and isinstance(instance, EmissaoPassagem):
        exclude_emissao_id = getattr(instance, "id", None)
    cpfs_sets_map = _build_cpfs_sets_map(empresa_id, exclude_emissao_id)
    data: Dict[int, List[dict]] = {}
    for conta in contas:
        key = conta.programa_id
        cpfs_usados_list = sorted(cpfs_sets_map.get(key, set()))
        cpfs_usados = len(cpfs_usados_list)
        limite_cpfs = _get_limite_cpfs(conta)
        cpfs_disponiveis = None if limite_cpfs is None else max(limite_cpfs - cpfs_usados, 0)
        data.setdefault(conta.conta_administrada_id, [])
        data[conta.conta_administrada_id].append(
            {
                "id": conta.programa_id,
                "nome": conta.programa.nome,
                "saldo": conta.saldo_pontos,
                "valor_medio": float(conta.valor_medio_por_mil or 0),
                "cpfs_disponiveis": cpfs_disponiveis,
                "cpfs_total": limite_cpfs,
                "cpfs_usados": cpfs_usados,
                "cpfs_usados_list": cpfs_usados_list,
            }
        )

    if instance and getattr(instance, "programa_id", None) and getattr(instance, "conta_administrada_id", None):
        if instance.conta_administrada_id not in data:
            data[instance.conta_administrada_id] = []
        if not any(p["id"] == instance.programa_id for p in data[instance.conta_administrada_id]):
            data[instance.conta_administrada_id].append(
                {
                    "id": instance.programa_id,
                    "nome": str(instance.programa),
                    "saldo": 0,
                    "valor_medio": 0,
                    "cpfs_disponiveis": instance.programa.quantidade_cpfs_disponiveis,
                    "cpfs_total": instance.programa.quantidade_cpfs_disponiveis,
                    "cpfs_usados": len(cpfs_sets_map.get(instance.programa_id, set())),
                    "cpfs_usados_list": sorted(cpfs_sets_map.get(instance.programa_id, set())),
                }
            )
    return data


def build_programas_fidelidade_map(
    empresa_id=None, exclude_emissao_id=None
) -> List[dict]:
    """Retorna uma lista de programas com informações de CPFs consolidadas."""

    programas = ProgramaFidelidade.objects.all().order_by("nome")
    cpfs_sets_map = _build_cpfs_sets_map(empresa_id, exclude_emissao_id)
    data: List[dict] = []
    for programa in programas:
        cpfs_usados_list = sorted(cpfs_sets_map.get(programa.id, set()))
        limite_cpfs = programa.quantidade_cpfs_disponiveis
        cpfs_disponiveis = None if limite_cpfs is None else max(limite_cpfs - len(cpfs_usados_list), 0)
        data.append(
            {
                "id": programa.id,
                "nome": programa.nome,
                "valor_medio": float(programa.preco_medio_milheiro or 0),
                "cpfs_disponiveis": cpfs_disponiveis,
                "cpfs_total": limite_cpfs,
                "cpfs_usados": len(cpfs_usados_list),
                "cpfs_usados_list": cpfs_usados_list,
            }
        )
    return data

"""Serviços para mapear programas vinculados a clientes."""

from typing import Dict, List

from gestao.models import ContaFidelidade


def build_clientes_programas_map(instance=None, empresa_id=None) -> Dict[int, List[dict]]:
    """Retorna um mapa ``cliente_id -> lista de programas e saldos``."""

    contas = ContaFidelidade.objects.filter(
        cliente__perfil="cliente",
        cliente__ativo=True,
        conta_administrada__isnull=True,
    ).select_related("programa", "cliente__usuario")
    if empresa_id:
        contas = contas.filter(cliente__empresa_id=empresa_id)
    data = {}
    for conta in contas:
        data.setdefault(conta.cliente_id, [])
        data[conta.cliente_id].append(
            {
                "id": conta.programa_id,
                "nome": conta.programa.nome,
                "saldo": conta.saldo_pontos,
                "valor_medio": float(conta.valor_medio_por_mil or 0),
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
                }
            )
    return data


def build_contas_administradas_programas_map(empresa_id=None, instance=None) -> Dict[int, List[dict]]:
    """Retorna um mapa ``conta_administrada_id -> lista de programas e saldos``."""

    contas = ContaFidelidade.objects.filter(
        conta_administrada__isnull=False,
        conta_administrada__ativo=True,
    ).select_related("programa", "conta_administrada")
    if empresa_id:
        contas = contas.filter(conta_administrada__empresa_id=empresa_id)

    data: Dict[int, List[dict]] = {}
    for conta in contas:
        data.setdefault(conta.conta_administrada_id, [])
        data[conta.conta_administrada_id].append(
            {
                "id": conta.programa_id,
                "nome": conta.programa.nome,
                "saldo": conta.saldo_pontos,
                "valor_medio": float(conta.valor_medio_por_mil or 0),
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
                }
            )
    return data

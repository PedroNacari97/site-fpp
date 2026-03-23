"""Serviços para validação e sincronização do controle de CPFs por conta."""

from collections.abc import Iterable
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from gestao.models import ContaFidelidade, UsoCPF
from gestao.utils import normalize_cpf


def _normalize_cpfs(cpfs: Iterable[str]) -> set[str]:
    normalized_cpfs = set()
    for cpf in cpfs:
        normalized = normalize_cpf(cpf)
        if normalized:
            normalized_cpfs.add(normalized)
    return normalized_cpfs


def _cpf_liberado(uso: UsoCPF) -> bool:
    programa = uso.conta_fidelidade.programa
    hoje = timezone.localdate()
    if programa.tipo_regra_reset == programa.REGRA_RESET_DIAS and programa.dias_reset:
        return hoje >= uso.data_ultima_emissao + timedelta(days=programa.dias_reset)
    return hoje.year > uso.data_ultima_emissao.year


def get_cpf_control_data(conta: ContaFidelidade | None):
    if conta is None:
        return None

    usos = list(conta.get_usos_cpf_queryset().order_by('cpf'))
    usados = sum(1 for uso in usos if not _cpf_liberado(uso))
    limite = conta.limite_cpfs
    disponiveis = None if limite is None else max(limite - usados, 0)
    tone = 'disponivel'
    label = 'Disponível'
    if limite is not None:
        if usados >= limite:
            tone = 'bloqueado'
            label = 'Bloqueado'
        elif limite and (usados / limite) >= 0.8:
            tone = 'proximo'
            label = 'Próximo do limite'
    return {
        'limite_cpfs': limite,
        'cpfs_usados': usados,
        'cpfs_disponiveis': disponiveis,
        'status': tone,
        'status_label': label,
        'usos': usos,
    }


def validar_limite_cpfs(conta: ContaFidelidade | None, cpfs: Iterable[str], emissao_id: int | None = None):
    if conta is None:
        return 0, None

    controle = get_cpf_control_data(conta)
    limite = controle['limite_cpfs']
    if limite is None:
        return 0, None

    existentes_bloqueados = {
        uso.cpf for uso in controle['usos'] if not _cpf_liberado(uso)
    }
    cpfs_na_emissao = _normalize_cpfs(cpfs)
    cpfs_novos = {cpf for cpf in cpfs_na_emissao if cpf not in existentes_bloqueados}
    cpfs_disponiveis = controle['cpfs_disponiveis']

    if len(cpfs_novos) > cpfs_disponiveis:
        raise ValidationError(
            f"Limite de CPFs excedido. Esta emissão adiciona {len(cpfs_novos)} CPF(s) novos, "
            f"mas restam apenas {cpfs_disponiveis} disponível(is) para a conta selecionada."
        )

    return len(cpfs_novos), cpfs_disponiveis


def registrar_uso_cpfs(conta: ContaFidelidade | None, cpfs: Iterable[str], data_emissao=None):
    if conta is None:
        return
    data_emissao = data_emissao or timezone.localdate()
    for cpf in _normalize_cpfs(cpfs):
        UsoCPF.objects.update_or_create(
            conta_fidelidade=conta,
            cpf=cpf,
            defaults={'data_ultima_emissao': data_emissao},
        )

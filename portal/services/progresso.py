"""Servico de calculo de progresso de estudo (Portal B2C).

Responsavel por computar quantos artigos (publicados) de um modulo um
`PortalUser` ja leu, devolvendo o percentual e o status textual usado
pelo template da barra de progresso.

Isolado do SaaS B2B — opera exclusivamente sobre `PortalUser`/`ProgressoArtigo`.
"""
from __future__ import annotations

from typing import Iterable, Optional

from django.db.models import Count

from portal.models import (
    ArtigoEstudo,
    ModuloEstudo,
    PortalUser,
    ProgressoArtigo,
)


STATUS_NAO_INICIADO = "nao_iniciado"
STATUS_EM_ANDAMENTO = "em_andamento"
STATUS_CONCLUIDO = "concluido"

STATUS_LABELS = {
    STATUS_NAO_INICIADO: "Comece agora",
    STATUS_EM_ANDAMENTO: "Em andamento",
    STATUS_CONCLUIDO: "Concluido",
}


def _vazio() -> dict:
    return {
        "total_artigos": 0,
        "lidos": 0,
        "percentual": 0,
        "status": STATUS_NAO_INICIADO,
        "status_label": STATUS_LABELS[STATUS_NAO_INICIADO],
    }


def _status_from(total: int, lidos: int) -> str:
    if total <= 0 or lidos <= 0:
        return STATUS_NAO_INICIADO
    if lidos >= total:
        return STATUS_CONCLUIDO
    return STATUS_EM_ANDAMENTO


def _payload(total: int, lidos: int) -> dict:
    if total <= 0:
        return _vazio()
    lidos = max(0, min(lidos, total))
    percentual = int(round((lidos / total) * 100))
    status = _status_from(total, lidos)
    return {
        "total_artigos": total,
        "lidos": lidos,
        "percentual": percentual,
        "status": status,
        "status_label": STATUS_LABELS[status],
    }


def calcular_progresso_modulo(
    user: Optional[PortalUser],
    modulo: ModuloEstudo,
) -> dict:
    """Calcula progresso do `user` no `modulo`.

    Retorna sempre um dict no formato:
        {
            "total_artigos": int,
            "lidos": int,
            "percentual": 0..100,
            "status": "nao_iniciado" | "em_andamento" | "concluido",
            "status_label": str,
        }

    Se `user` for None (anonimo), retorna estado vazio mas com `total_artigos`
    preenchido corretamente — os templates nao renderizam a barra nesse caso.
    """
    total = ArtigoEstudo.objects.filter(modulo=modulo, status="published").count()

    if user is None or not getattr(user, "is_authenticated", False):
        payload = _vazio()
        payload["total_artigos"] = total
        return payload

    lidos = (
        ProgressoArtigo.objects.filter(
            user=user,
            artigo__modulo=modulo,
            artigo__status="published",
            lido_em__isnull=False,
        )
        .values("artigo_id")
        .distinct()
        .count()
    )
    return _payload(total, lidos)


def anotar_progresso_em_modulos(
    user: Optional[PortalUser],
    modulos: Iterable[ModuloEstudo],
) -> list[ModuloEstudo]:
    """Anota cada modulo com `.progresso = {dict}` e `.total_artigos`.

    Evita N+1 fazendo 2 queries:
    - uma agregada para contar artigos publicados por modulo
    - outra agregada para contar artigos lidos (se user logado)

    Retorna a lista de modulos (ja iterada) na mesma ordem recebida.
    """
    modulos_list = list(modulos)
    if not modulos_list:
        return modulos_list

    ids = [m.pk for m in modulos_list]

    totais = dict(
        ArtigoEstudo.objects.filter(
            modulo_id__in=ids,
            status="published",
        )
        .values_list("modulo_id")
        .annotate(n=Count("id"))
        .values_list("modulo_id", "n")
    )

    lidos_map: dict[int, int] = {}
    if user is not None and getattr(user, "is_authenticated", False):
        # lidos = ProgressoArtigo com lido_em IS NOT NULL, agrupado por modulo
        progressos_por_modulo = (
            ProgressoArtigo.objects.filter(
                user=user,
                artigo__modulo_id__in=ids,
                artigo__status="published",
                lido_em__isnull=False,
            )
            .values_list("artigo__modulo_id")
            .annotate(n=Count("id", distinct=True))
            .values_list("artigo__modulo_id", "n")
        )
        lidos_map = dict(progressos_por_modulo)

    for m in modulos_list:
        total = int(totais.get(m.pk, 0))
        lidos = int(lidos_map.get(m.pk, 0))
        m.total_artigos = total
        m.progresso = _payload(total, lidos)

    return modulos_list


def ids_artigos_lidos(
    user: Optional[PortalUser],
    modulo: ModuloEstudo,
) -> set[int]:
    """Retorna set com `artigo_id` ja lidos pelo user no modulo (ou vazio)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return set()
    return set(
        ProgressoArtigo.objects.filter(
            user=user,
            artigo__modulo=modulo,
            lido_em__isnull=False,
        ).values_list("artigo_id", flat=True)
    )


def anotar_lido_em_artigos(
    user: Optional[PortalUser],
    artigos: Iterable[ArtigoEstudo],
) -> list[ArtigoEstudo]:
    """Anota cada artigo com `.lido_pelo_user: bool` (False se anonimo)."""
    artigos_list = list(artigos)
    if not artigos_list:
        return artigos_list

    lidos: set[int] = set()
    if user is not None and getattr(user, "is_authenticated", False):
        ids = [a.pk for a in artigos_list]
        lidos = set(
            ProgressoArtigo.objects.filter(
                user=user,
                artigo_id__in=ids,
                lido_em__isnull=False,
            ).values_list("artigo_id", flat=True)
        )
    for a in artigos_list:
        a.lido_pelo_user = a.pk in lidos
    return artigos_list

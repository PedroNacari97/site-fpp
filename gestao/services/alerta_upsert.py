from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from gestao.models import AlertaViagem


def _normalize_key_part(value):
    return " ".join(str(value or "").strip().lower().split())


def build_alerta_match_key(data):
    return {
        "origem": _normalize_key_part(data.get("origem")),
        "destino": _normalize_key_part(data.get("destino")),
        "classe": _normalize_key_part(data.get("classe")),
        "programa_fidelidade": _normalize_key_part(data.get("programa_fidelidade")),
        "companhia_aerea": _normalize_key_part(data.get("companhia_aerea")),
    }


def find_matching_alerta(data):
    match_key = build_alerta_match_key(data)
    if not all(match_key.values()):
        return None
    return (
        AlertaViagem.objects.filter(
            origem__iexact=match_key["origem"],
            destino__iexact=match_key["destino"],
            classe__iexact=match_key["classe"],
            programa_fidelidade__iexact=match_key["programa_fidelidade"],
            companhia_aerea__iexact=match_key["companhia_aerea"],
        )
        .order_by("-criado_em", "-id")
        .first()
    )


def _merge_date_lists(existing_dates, incoming_dates):
    merged = []
    seen = set()
    for raw_date in [*(existing_dates or []), *(incoming_dates or [])]:
        value = str(raw_date or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        merged.append(value)
    return sorted(merged)


def _coerce_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def serialize_alerta_payload(data):
    raw = deepcopy(data)
    payload = {
        "titulo": str(raw.get("titulo") or "").strip(),
        "conteudo": str(raw.get("conteudo") or "").strip(),
        "continente": str(raw.get("continente") or "").strip(),
        "pais": str(raw.get("pais") or "").strip(),
        "cidade_destino": str(raw.get("cidade_destino") or "").strip(),
        "origem": str(raw.get("origem") or "").strip().upper(),
        "destino": str(raw.get("destino") or "").strip().upper(),
        "classe": str(raw.get("classe") or "").strip(),
        "programa_fidelidade": str(raw.get("programa_fidelidade") or "").strip(),
        "companhia_aerea": str(raw.get("companhia_aerea") or "").strip(),
        "valor_milhas": _coerce_int(raw.get("valor_milhas")),
        "valor_reais": _coerce_decimal(raw.get("valor_reais")),
        "datas_ida": _merge_date_lists([], raw.get("datas_ida") or []),
        "datas_volta": _merge_date_lists([], raw.get("datas_volta") or []),
        "manter_apos_cinco_dias": bool(raw.get("manter_apos_cinco_dias", False)),
        "ocultar_apos_datas": bool(raw.get("ocultar_apos_datas", False)),
        "ativo": bool(raw.get("ativo", True)),
    }
    return payload


def _validate_alerta_payload(payload):
    if not payload.get("valor_milhas"):
        raise ValueError("Valor em milhas obrigatorio para publicar alerta.")


def create_or_update_alerta(data):
    payload = serialize_alerta_payload(data)
    _validate_alerta_payload(payload)
    existing = find_matching_alerta(payload)
    now = timezone.now()

    if existing:
        from portal.services.alert_email_broadcasts import (
            capture_alert_email_snapshot,
            notify_alert_subscribers,
        )

        previous_snapshot = capture_alert_email_snapshot(existing)
        existing.titulo = payload["titulo"] or existing.titulo
        existing.conteudo = payload["conteudo"] or existing.conteudo
        existing.continente = payload["continente"] or existing.continente
        existing.pais = payload["pais"] or existing.pais
        existing.cidade_destino = payload["cidade_destino"] or existing.cidade_destino
        existing.origem = payload["origem"] or existing.origem
        existing.destino = payload["destino"] or existing.destino
        existing.classe = payload["classe"] or existing.classe
        existing.programa_fidelidade = payload["programa_fidelidade"] or existing.programa_fidelidade
        existing.companhia_aerea = payload["companhia_aerea"] or existing.companhia_aerea
        existing.valor_milhas = payload["valor_milhas"] if payload["valor_milhas"] is not None else existing.valor_milhas
        existing.valor_reais = payload["valor_reais"] if payload["valor_reais"] is not None else existing.valor_reais
        existing.datas_ida = _merge_date_lists(existing.datas_ida, payload["datas_ida"])
        existing.datas_volta = _merge_date_lists(existing.datas_volta, payload["datas_volta"])
        existing.manter_apos_cinco_dias = payload["manter_apos_cinco_dias"] or existing.manter_apos_cinco_dias
        existing.ocultar_apos_datas = payload["ocultar_apos_datas"] or existing.ocultar_apos_datas
        existing.ativo = True
        existing.criado_em = now
        existing.save(
            update_fields=[
                "titulo",
                "conteudo",
                "continente",
                "pais",
                "cidade_destino",
                "origem",
                "destino",
                "classe",
                "programa_fidelidade",
                "companhia_aerea",
                "valor_milhas",
                "valor_reais",
                "datas_ida",
                "datas_volta",
                "manter_apos_cinco_dias",
                "ocultar_apos_datas",
                "ativo",
                "criado_em",
            ]
        )
        notify_alert_subscribers(existing, created=False, previous_snapshot=previous_snapshot)
        return existing, False

    alerta = AlertaViagem.objects.create(**payload)
    from portal.services.alert_email_broadcasts import notify_alert_subscribers

    notify_alert_subscribers(alerta, created=True)
    return alerta, True

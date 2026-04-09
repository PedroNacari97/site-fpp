from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from typing import Any, Iterable

from django.urls import reverse

from gestao.models import Aeroporto, AlertaViagem
from gestao.models.companhia_aerea import CompanhiaAerea
from portal.services.ai_pipeline import _extract_response_text, _openai_request
from portal.templatetags.portal_extras import repair_portuguese_text


ALERTA_PUBLIC_MODEL = os.environ.get("OPENAI_ALERT_PUBLIC_MODEL", "gpt-5.4-mini")
ALERTA_COPY_ENABLED = os.environ.get("PORTAL_GENERATE_AI_ALERT_COPY", "1").lower() in {"1", "true", "yes", "on"}
PUBLIC_HOME_ALERT_MAX_AGE_DAYS = 15

PROGRAM_URL_MAP = {
    "latam": "https://www.latamairlines.com/br/pt/latam-pass",
    "latam pass": "https://www.latamairlines.com/br/pt/latam-pass",
    "latampass": "https://www.latamairlines.com/br/pt/latam-pass",
    "smiles": "https://www.smiles.com.br",
    "azul fidelidade": "https://www.voeazul.com.br/br/pt/programa-fidelidade",
    "tudoazul": "https://www.voeazul.com.br/br/pt/programa-fidelidade",
    "livelo": "https://www.livelo.com.br",
    "esfera": "https://www.esfera.com.vc",
    "inter": "https://www.inter.co",
    "ibeira plus": "https://www.iberia.com/br/iberiaplus/",
    "iberia plus": "https://www.iberia.com/br/iberiaplus/",
    "executive club": "https://www.britishairways.com/travel/executive-club/public/en_br",
    "miles&go": "https://www.flytap.com/pt-br/miles-and-go",
    "tap miles&go": "https://www.flytap.com/pt-br/miles-and-go",
    "connectmiles": "https://www.connectmiles.com",
    "aadvantage": "https://www.aa.com/aadvantage-program/",
}

PROGRAM_MILE_VALUE_MAP = {
    "latam": Decimal("28"),
    "latam pass": Decimal("28"),
    "latampass": Decimal("28"),
    "smiles": Decimal("18"),
    "azul": Decimal("18"),
    "azul fidelidade": Decimal("18"),
    "tudoazul": Decimal("18"),
    "azul pelo mundo": Decimal("17"),
}

MONTH_LABELS = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}


def _normalize_key(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _airport_city(iata: str, fallback: str = "") -> str:
    if not iata:
        return fallback
    airport = Aeroporto.objects.filter(sigla__iexact=iata).order_by("id").first()
    if airport and airport.cidade:
        return repair_portuguese_text(airport.cidade)
    if airport and airport.nome:
        return repair_portuguese_text(airport.nome)
    return repair_portuguese_text(fallback or iata)


def _format_milhas(value: int | None) -> str:
    if not value:
        return "Consulte o programa"
    return f"{value:,.0f}".replace(",", ".")


def _format_milhas_alerta(value: int | None, *, include_suffix: bool = True) -> str:
    if not value:
        return "Consulte o programa"
    label = f"a partir de {_format_milhas(value)}"
    return f"{label} milhas" if include_suffix else label


def _format_money(value) -> str:
    if value in (None, ""):
        return ""
    return f"R$ {value}"


def _estimate_points_cash_value(alerta: AlertaViagem) -> str:
    if not alerta.valor_milhas:
        return ""

    rate_per_thousand = PROGRAM_MILE_VALUE_MAP.get(_normalize_key(alerta.programa_fidelidade))
    if rate_per_thousand is None:
        return ""

    estimated_total = (
        (Decimal(alerta.valor_milhas) / Decimal("1000")) * rate_per_thousand
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return _format_money(f"{estimated_total:,.0f}".replace(",", "."))


def _format_date_short(value: date | None) -> str:
    if not value:
        return ""
    return value.strftime("%d/%m")


def _format_date_long(value: date) -> str:
    return f"{value.day:02d} de {MONTH_LABELS[value.month].lower()} de {value.year}"


def _parse_iso_dates(values) -> list[date]:
    parsed: list[date] = []
    seen = set()
    for raw in values or []:
        try:
            parsed_date = date.fromisoformat(str(raw))
        except (TypeError, ValueError):
            continue
        if parsed_date in seen:
            continue
        seen.add(parsed_date)
        parsed.append(parsed_date)
    return sorted(parsed)


def _group_dates(values) -> list[dict[str, Any]]:
    parsed = _parse_iso_dates(values)
    grouped: dict[tuple[int, int], list[date]] = {}
    for item in parsed:
        grouped.setdefault((item.year, item.month), []).append(item)
    results = []
    for (year, month), items in grouped.items():
        results.append(
            {
                "label": f"{MONTH_LABELS[month]}/{str(year)[2:]}",
                "full_label": f"{MONTH_LABELS[month]} {year}",
                "days": [f"{entry.day:02d}" for entry in items],
                "dates": [_format_date_long(entry) for entry in items],
            }
        )
    return results


def _build_route_summary(alerta: AlertaViagem) -> dict[str, str]:
    origem_cidade = _airport_city(alerta.origem)
    destino_cidade = repair_portuguese_text(alerta.cidade_destino or _airport_city(alerta.destino))
    return {
        "origem_codigo": (alerta.origem or "").upper(),
        "destino_codigo": (alerta.destino or "").upper(),
        "origem_cidade": origem_cidade,
        "destino_cidade": destino_cidade,
        "route_label": f"{origem_cidade} → {destino_cidade}",
        "route_search_label": f"{(alerta.origem or '').upper()}-{(alerta.destino or '').upper()}",
    }


def _build_airport_lookup(alertas: Iterable[AlertaViagem]) -> dict[str, str]:
    normalized_iatas = {
        str(code).strip().upper()
        for alerta in alertas
        for code in (alerta.origem, alerta.destino)
        if str(code or "").strip()
    }
    if not normalized_iatas:
        return {}

    lookup: dict[str, str] = {}
    for airport in Aeroporto.objects.filter(sigla__in=normalized_iatas).order_by("sigla", "id"):
        code = str(airport.sigla or "").strip().upper()
        if not code or code in lookup:
            continue
        if airport.cidade:
            lookup[code] = repair_portuguese_text(airport.cidade)
            continue
        if airport.nome:
            lookup[code] = repair_portuguese_text(airport.nome)
    return lookup


def _build_route_summary_with_lookup(alerta: AlertaViagem, airport_lookup: dict[str, str] | None = None) -> dict[str, str]:
    airport_lookup = airport_lookup or {}
    origem_codigo = (alerta.origem or "").upper()
    destino_codigo = (alerta.destino or "").upper()
    origem_cidade = airport_lookup.get(origem_codigo) or _airport_city(alerta.origem)
    destino_cidade = repair_portuguese_text(
        alerta.cidade_destino or airport_lookup.get(destino_codigo) or _airport_city(alerta.destino)
    )
    return {
        "origem_codigo": origem_codigo,
        "destino_codigo": destino_codigo,
        "origem_cidade": origem_cidade,
        "destino_cidade": destino_cidade,
        "route_label": f"{origem_cidade} → {destino_cidade}",
        "route_search_label": f"{origem_codigo}-{destino_codigo}",
    }


def _resolve_program_url(alerta: AlertaViagem) -> str:
    program_key = _normalize_key(alerta.programa_fidelidade)
    if program_key in PROGRAM_URL_MAP:
        return PROGRAM_URL_MAP[program_key]

    for known_key, known_url in PROGRAM_URL_MAP.items():
        if program_key and (program_key in known_key or known_key in program_key):
            return known_url

    companhia = (
        CompanhiaAerea.objects.filter(nome__iexact=alerta.companhia_aerea).order_by("id").first()
        if alerta.companhia_aerea
        else None
    )
    if companhia and companhia.site_url:
        return companhia.site_url
    return ""


def list_visible_public_alerts(limit: int | None = None, *, max_age_days: int = 5) -> list[AlertaViagem]:
    visible = [
        alerta
        for alerta in AlertaViagem.objects.filter(ativo=True).order_by("-criado_em")
        if alerta.deve_aparecer_na_vitrine(max_age_days=max_age_days) and alerta.valor_milhas
    ]
    return visible[:limit] if limit else visible


def build_public_alert_card(alerta: AlertaViagem) -> dict[str, Any]:
    route = _build_route_summary(alerta)
    all_dates = alerta.datas_disponiveis_validas()
    has_miles = bool(alerta.valor_milhas)
    estimated_cash_value = _estimate_points_cash_value(alerta)
    return {
        "id": alerta.id,
        "url": reverse("portal_alerta_detalhe", args=[alerta.id]),
        "origem_codigo": route["origem_codigo"],
        "destino_codigo": route["destino_codigo"],
        "origem_cidade": route["origem_cidade"],
        "destino_cidade": route["destino_cidade"],
        "route_label": route["route_label"],
        "classe_label": alerta.get_classe_display(),
        "programa": repair_portuguese_text(alerta.programa_fidelidade),
        "companhia": repair_portuguese_text(alerta.companhia_aerea),
        "miles_label": f"{_format_milhas(alerta.valor_milhas)} milhas" if has_miles else "Consulte o programa",
        "miles_kicker": "A partir de" if has_miles else "Quantidade de milhas",
        "estimated_cash_value": estimated_cash_value,
        "validade_label": f"Até {_format_date_short(all_dates[-1])}" if all_dates else "",
        "tem_datas_volta": bool(alerta.datas_volta),
    }


def build_public_alert_cards(alertas: Iterable[AlertaViagem]) -> list[dict[str, Any]]:
    alerts = list(alertas)
    if not alerts:
        return []

    airport_lookup = _build_airport_lookup(alerts)
    cards = []
    for alerta in alerts:
        route = _build_route_summary_with_lookup(alerta, airport_lookup)
        all_dates = alerta.datas_disponiveis_validas()
        has_miles = bool(alerta.valor_milhas)
        cards.append(
            {
                "id": alerta.id,
                "url": reverse("portal_alerta_detalhe", args=[alerta.id]),
                "origem_codigo": route["origem_codigo"],
                "destino_codigo": route["destino_codigo"],
                "origem_cidade": route["origem_cidade"],
                "destino_cidade": route["destino_cidade"],
                "route_label": route["route_label"],
                "classe_label": alerta.get_classe_display(),
                "programa": repair_portuguese_text(alerta.programa_fidelidade),
                "companhia": repair_portuguese_text(alerta.companhia_aerea),
                "miles_label": f"{_format_milhas(alerta.valor_milhas)} milhas" if has_miles else "Consulte o programa",
                "miles_kicker": "A partir de" if has_miles else "Quantidade de milhas",
                "estimated_cash_value": _estimate_points_cash_value(alerta),
                "validade_label": f"Até {_format_date_short(all_dates[-1])}" if all_dates else "",
                "tem_datas_volta": bool(alerta.datas_volta),
            }
        )
    return cards


def build_similar_alert_cards(alerta: AlertaViagem, limit: int = 3, *, max_age_days: int = 5) -> list[dict[str, Any]]:
    candidates = []
    for item in list_visible_public_alerts(max_age_days=max_age_days):
        if item.id == alerta.id:
            continue
        score = 0
        if _normalize_key(item.programa_fidelidade) == _normalize_key(alerta.programa_fidelidade):
            score += 3
        if _normalize_key(item.continente) == _normalize_key(alerta.continente):
            score += 2
        if _normalize_key(item.classe) == _normalize_key(alerta.classe):
            score += 2
        if _normalize_key(item.origem) == _normalize_key(alerta.origem):
            score += 1
        if _normalize_key(item.destino) == _normalize_key(alerta.destino):
            score += 1
        candidates.append((score, item.criado_em, item))

    candidates.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return build_public_alert_cards([item for _, _, item in candidates[:limit]])


def _alert_signature(alerta: AlertaViagem) -> str:
    payload = {
        "id": alerta.id,
        "titulo": alerta.titulo,
        "conteudo": alerta.conteudo,
        "continente": alerta.continente,
        "pais": alerta.pais,
        "cidade_destino": alerta.cidade_destino,
        "origem": alerta.origem,
        "destino": alerta.destino,
        "classe": alerta.classe,
        "programa_fidelidade": alerta.programa_fidelidade,
        "companhia_aerea": alerta.companhia_aerea,
        "valor_milhas": alerta.valor_milhas,
        "valor_reais": str(alerta.valor_reais or ""),
        "datas_ida": list(alerta.datas_ida or []),
        "datas_volta": list(alerta.datas_volta or []),
        "criado_em": alerta.criado_em.isoformat() if alerta.criado_em else "",
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _fallback_public_copy(alerta: AlertaViagem) -> dict[str, Any]:
    route = _build_route_summary(alerta)
    classe = alerta.get_classe_display().lower()
    programa = repair_portuguese_text(alerta.programa_fidelidade or "programa informado no alerta")
    companhia = repair_portuguese_text(alerta.companhia_aerea or "companhia informada no alerta")
    miles_with_prefix = _format_milhas_alerta(alerta.valor_milhas)
    datas_ida = _group_dates(alerta.datas_ida)
    datas_volta = _group_dates(alerta.datas_volta)
    route_search = route["route_search_label"]

    hero_title = repair_portuguese_text(
        alerta.titulo or f"{route['origem_cidade']} para {route['destino_cidade']} {miles_with_prefix}"
    )
    if alerta.valor_milhas:
        about_offer = (
            f"Excelente oportunidade para emitir o trecho {route['route_label']} em classe {classe} "
            f"pelo programa {programa}. O valor observado neste alerta ficou {miles_with_prefix} por pessoa"
        )
    else:
        about_offer = (
            f"Excelente oportunidade para emitir o trecho {route['route_label']} em classe {classe} "
            f"pelo programa {programa}. Consulte o programa para validar a pontuação por pessoa"
        )
    if alerta.valor_reais:
        about_offer += f", alem das taxas estimadas em {_format_money(alerta.valor_reais)}"
    about_offer += "."

    benefits = [
        f"{miles_with_prefix} por pessoa" if alerta.valor_milhas else "Consulte o programa para validar a pontuação",
        f"Trecho operado por {companhia}",
        f"Busca direta no programa {programa}",
        "Datas organizadas para consulta rápida",
    ]

    steps = [
        {
            "title": f"Acesse sua conta do programa {programa}",
            "description": f"Entre na sua conta do {programa} para pesquisar e concluir a emissão.",
        },
        {
            "title": "Busque a disponibilidade",
            "description": f"Pesquise o trecho {route_search} nas datas listadas neste alerta.",
        },
        {
            "title": "Confira o valor em milhas",
            "description": (
                f"Valide se o trecho continua aparecendo com valor {miles_with_prefix} por pessoa."
                if alerta.valor_milhas
                else "Valide no programa a pontuação exigida antes de concluir a emissão."
            ),
        },
        {
            "title": "Finalize o resgate",
            "description": f"Conclua a emissão diretamente no programa {programa} e confirme os dados da viagem.",
        },
    ]

    return {
        "hero_title": hero_title,
        "hero_subtitle": route["route_label"],
        "about_offer": about_offer,
        "benefits": benefits,
        "steps": steps,
        "ida_groups": datas_ida,
        "volta_groups": datas_volta,
    }


@lru_cache(maxsize=128)
def _build_ai_public_copy(signature: str) -> dict[str, Any]:
    if not ALERTA_COPY_ENABLED or not os.environ.get("OPENAI_API_KEY"):
        return {}

    payload_json = json.loads(signature)
    route = _build_route_summary(type("AlertProxy", (), payload_json))
    payload = {
        "model": ALERTA_PUBLIC_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Você escreve a camada pública de um alerta de passagem aérea para um portal editorial brasileiro. "
                            "Retorne JSON com hero_title, hero_subtitle, about_offer, benefits e steps. "
                            "Os textos precisam ser claros, comerciais e coerentes com os dados reais do alerta. "
                            "Não invente bagagem, cancelamento, remarcação, lounge, franquia ou qualquer benefício que não esteja confirmado nos dados. "
                            "Em benefits, entregue exatamente 4 itens curtos e seguros. "
                            "Em steps, entregue exatamente 4 etapas com title e description objetivas, orientadas à emissão no programa. "
                            "Escreva em português do Brasil, sem emojis e sem exagero publicitário. "
                            "Antes de responder, revise ortografia, acentuação, concordância e fluidez em PT-BR. "
                            "Corrija qualquer erro de português antes de devolver o JSON final."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {
                                "titulo": payload_json.get("titulo"),
                                "rota": route["route_label"],
                                "origem": payload_json.get("origem"),
                                "destino": payload_json.get("destino"),
                                "classe": payload_json.get("classe"),
                                "programa": payload_json.get("programa_fidelidade"),
                                "companhia": payload_json.get("companhia_aerea"),
                                "valor_milhas": payload_json.get("valor_milhas"),
                                "valor_reais": payload_json.get("valor_reais"),
                                "datas_ida": payload_json.get("datas_ida"),
                                "datas_volta": payload_json.get("datas_volta"),
                            },
                            ensure_ascii=False,
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "portal_alert_public_copy",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "hero_title": {"type": "string"},
                        "hero_subtitle": {"type": "string"},
                        "about_offer": {"type": "string"},
                        "benefits": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 4,
                            "maxItems": 4,
                        },
                        "steps": {
                            "type": "array",
                            "minItems": 4,
                            "maxItems": 4,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "title": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                                "required": ["title", "description"],
                            },
                        },
                    },
                    "required": ["hero_title", "hero_subtitle", "about_offer", "benefits", "steps"],
                },
            }
        },
    }

    try:
        response_json = _openai_request(payload)
        content = _extract_response_text(response_json)
        parsed = json.loads(content)
        return {
            "hero_title": repair_portuguese_text(parsed.get("hero_title") or ""),
            "hero_subtitle": repair_portuguese_text(parsed.get("hero_subtitle") or ""),
            "about_offer": repair_portuguese_text(parsed.get("about_offer") or ""),
            "benefits": [repair_portuguese_text(item) for item in parsed.get("benefits") or []][:4],
            "steps": [
                {
                    "title": repair_portuguese_text(item.get("title") or ""),
                    "description": repair_portuguese_text(item.get("description") or ""),
                }
                for item in (parsed.get("steps") or [])[:4]
            ],
        }
    except Exception:
        return {}


def build_public_alert_detail(alerta: AlertaViagem) -> dict[str, Any]:
    route = _build_route_summary(alerta)
    signature = _alert_signature(alerta)
    fallback = _fallback_public_copy(alerta)
    ai_copy = _build_ai_public_copy(signature)
    merged = {
        "hero_title": ai_copy.get("hero_title") or fallback["hero_title"],
        "hero_subtitle": ai_copy.get("hero_subtitle") or fallback["hero_subtitle"],
        "about_offer": ai_copy.get("about_offer") or fallback["about_offer"],
        "benefits": ai_copy.get("benefits") or fallback["benefits"],
        "steps": ai_copy.get("steps") or fallback["steps"],
        "ida_groups": fallback["ida_groups"],
        "volta_groups": fallback["volta_groups"],
        "cta_url": _resolve_program_url(alerta),
        "cta_label": f"Resgatar em {repair_portuguese_text(alerta.programa_fidelidade)}",
        "programa": repair_portuguese_text(alerta.programa_fidelidade),
        "companhia": repair_portuguese_text(alerta.companhia_aerea),
        "classe_label": alerta.get_classe_display(),
        "miles_label": f"{_format_milhas(alerta.valor_milhas)} milhas" if alerta.valor_milhas else "Consulte o programa",
        "miles_kicker": "A partir de" if alerta.valor_milhas else "Quantidade de milhas",
        "miles_caption": "por pessoa" if alerta.valor_milhas else "",
        "estimated_cash_value": _estimate_points_cash_value(alerta),
        "money_label": _format_money(alerta.valor_reais),
        "validade_label": f"Até {_format_date_short(alerta.ultima_data_disponivel())}" if alerta.ultima_data_disponivel() else "",
        "origem_codigo": route["origem_codigo"],
        "destino_codigo": route["destino_codigo"],
        "origem_cidade": route["origem_cidade"],
        "destino_cidade": route["destino_cidade"],
        "route_label": route["route_label"],
    }
    return merged

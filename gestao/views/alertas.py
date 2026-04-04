import json
import re
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from ..forms import AlertaViagemForm
from ..models import Aeroporto, AlertaViagem
from ..services.aeroporto_localizacao import serialize_airport_for_alerts
from ..services.alerta_parser import backfill_alerta_post_data, parse_alerta_bruto
from ..services.interesses_viagem import sync_alerta_interest_matches
from ..services.alerta_upsert import create_or_update_alerta
from ..services.telegram_alertas import (
    get_telegram_alertas_config,
    process_telegram_alert_update,
)
from .permissions import require_admin_or_operator


def _require_superuser(request):
    if not request.user.is_superuser:
        return render(request, "sem_permissao.html")
    return None


def _extract_link(conteudo):
    if not conteudo:
        return None
    match = re.search(r"(https?://\S+)", conteudo)
    return match.group(1) if match else None


def _query_with(params, **updates):
    base = {key: value for key, value in params.items() if value not in ("", None)}
    for key, value in updates.items():
        if value in ("", None):
            base.pop(key, None)
        else:
            base[key] = value
    return urlencode(base)


def _resolve_alert_back_url(request):
    requested = (request.GET.get("next") or "").strip()
    allowed_prefixes = (
        reverse("admin_alertas_passagens"),
        reverse("alertas_passagens"),
    )
    if requested and requested.startswith(allowed_prefixes):
        return requested
    referer = request.META.get("HTTP_REFERER", "")
    if referer:
        for prefix in allowed_prefixes:
            if prefix in referer:
                return referer.split(request.get_host(), 1)[-1] if request.get_host() in referer else prefix
    return reverse("admin_alertas_passagens")


def _alerta_time_ago(alerta):
    delta = timezone.now() - alerta.criado_em
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 60:
        return f"Ha {max(total_minutes, 1)} min"
    total_hours = total_minutes // 60
    if total_hours < 24:
        return f"Ha {total_hours} hora(s)"
    total_days = total_hours // 24
    return f"Ha {total_days} dia(s)"


def _alerta_periodo(alerta):
    months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    raw_date = None
    if alerta.datas_ida:
        raw_date = alerta.datas_ida[0]
    elif alerta.datas_volta:
        raw_date = alerta.datas_volta[0]
    if raw_date:
        try:
            parsed = date.fromisoformat(raw_date)
            return f"{months[parsed.month - 1]} {parsed.year}"
        except ValueError:
            return raw_date
    created = timezone.localtime(alerta.criado_em)
    return f"{months[created.month - 1]} {created.year}"


def _normalize_text(value):
    text = (value or "").lower()
    return (
        text.replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )


def _alerta_meta(alerta):
    text = _normalize_text(f"{alerta.titulo or ''} {alerta.conteudo or ''}")

    if any(token in text for token in ["baixa", "esgot", "limitad", "urgente", "critic"]):
        availability_label = "Baixa disponibilidade"
        availability_tone = "low"
    elif any(token in text for token in ["alta", "excelente", "aberta"]):
        availability_label = "Alta disponibilidade"
        availability_tone = "high"
    else:
        availability_label = "Media disponibilidade"
        availability_tone = "medium"

    if any(token in text for token in ["pior", "queda", "reduz", "baixa"]):
        trend_label = "Piorando"
        trend_tone = "worsening"
    elif any(token in text for token in ["melhor", "subiu", "aument", "recuper"]):
        trend_label = "Melhorando"
        trend_tone = "improving"
    else:
        trend_label = "Estavel"
        trend_tone = "stable"

    is_favorite = (
        "favorit" in text
        or (alerta.ativo and availability_tone in {"high", "medium"} and trend_tone != "worsening")
    )

    return {
        "availability_label": availability_label,
        "availability_tone": availability_tone,
        "trend_label": trend_label,
        "trend_tone": trend_tone,
        "is_favorite": is_favorite,
        "periodo": _alerta_periodo(alerta),
        "time_ago": _alerta_time_ago(alerta),
    }


def _alertas_vitrine_queryset():
    alertas_ativos = list(AlertaViagem.objects.filter(ativo=True).order_by("-criado_em"))
    visible_ids = [alerta.id for alerta in alertas_ativos if alerta.deve_aparecer_na_vitrine()]
    return AlertaViagem.objects.filter(id__in=visible_ids, ativo=True).order_by("-criado_em")


@login_required
def admin_alertas_passagens(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied

    if request.method == "POST":
        alerta = get_object_or_404(AlertaViagem, id=request.POST.get("alerta_id"))
        alerta.manter_apos_cinco_dias = request.POST.get("manter_apos_cinco_dias") == "on"
        alerta.ocultar_apos_datas = request.POST.get("ocultar_apos_datas") == "on"
        alerta.save(update_fields=["manter_apos_cinco_dias", "ocultar_apos_datas"])
        messages.success(request, "Regras de exibicao do alerta atualizadas.")
        redirect_to = (request.POST.get("next") or "").strip()
        if redirect_to.startswith(reverse("admin_alertas_passagens")):
            return redirect(redirect_to)
        return redirect("admin_alertas_passagens")

    all_alerts = AlertaViagem.objects.all().order_by("-criado_em")

    selected_continente = request.GET.get("continente") or None
    selected_pais = request.GET.get("pais") or None
    selected_cidade = request.GET.get("cidade") or None
    selected_programa = request.GET.get("programa") or ""
    selected_classe = request.GET.get("classe") or ""
    selected_status = request.GET.get("status_alerta") or "ativos"
    search_query = (request.GET.get("q") or "").strip()

    continentes = list(all_alerts.values_list("continente", flat=True).distinct().order_by("continente"))
    if selected_continente not in continentes:
        selected_continente = None

    paises_qs = all_alerts
    if selected_continente:
        paises_qs = paises_qs.filter(continente=selected_continente)
    paises = list(paises_qs.values_list("pais", flat=True).distinct().order_by("pais"))
    if selected_pais not in paises:
        selected_pais = None

    cidades_qs = paises_qs
    if selected_pais:
        cidades_qs = cidades_qs.filter(pais=selected_pais)
    cidades = list(cidades_qs.values_list("cidade_destino", flat=True).distinct().order_by("cidade_destino"))
    if selected_cidade not in cidades:
        selected_cidade = None

    filtered_alerts = all_alerts
    if selected_continente:
        filtered_alerts = filtered_alerts.filter(continente=selected_continente)
    if selected_pais:
        filtered_alerts = filtered_alerts.filter(pais=selected_pais)
    if selected_cidade:
        filtered_alerts = filtered_alerts.filter(cidade_destino=selected_cidade)
    if selected_programa:
        filtered_alerts = filtered_alerts.filter(programa_fidelidade=selected_programa)
    if selected_classe:
        filtered_alerts = filtered_alerts.filter(classe=selected_classe)
    if search_query:
        filtered_alerts = filtered_alerts.filter(
            Q(titulo__icontains=search_query)
            | Q(conteudo__icontains=search_query)
            | Q(origem__icontains=search_query)
            | Q(destino__icontains=search_query)
            | Q(cidade_destino__icontains=search_query)
            | Q(programa_fidelidade__icontains=search_query)
            | Q(companhia_aerea__icontains=search_query)
        )

    alert_cards = []
    detail_back_target = request.get_full_path()
    improving_count = 0
    favorites_count = 0
    resolved_count = 0
    recent_count = 0
    critical_count = 0

    for alerta in filtered_alerts:
        meta = _alerta_meta(alerta)

        if selected_status == "ativos" and not alerta.ativo:
            continue
        if selected_status == "resolvidos" and alerta.ativo:
            continue
        if selected_status == "favoritos" and not meta["is_favorite"]:
            continue
        if selected_status == "melhorando" and meta["trend_tone"] != "improving":
            continue
        if selected_status == "piorando" and meta["trend_tone"] != "worsening":
            continue
        if selected_status == "estavel" and meta["trend_tone"] != "stable":
            continue

        if meta["trend_tone"] == "improving":
            improving_count += 1
        if meta["is_favorite"]:
            favorites_count += 1
        if not alerta.ativo:
            resolved_count += 1
        if timezone.now() - alerta.criado_em <= timedelta(days=1):
            recent_count += 1
        if meta["availability_tone"] == "low" and alerta.ativo:
            critical_count += 1

        alert_cards.append(
            {
                "alerta": alerta,
                "meta": meta,
                "periodo": meta["periodo"],
                "time_ago": meta["time_ago"],
                "detail_url": (
                    f"{reverse('alerta_passagem_detalhe', args=[alerta.id])}?{urlencode({'next': detail_back_target})}"
                    if alerta.ativo
                    else (reverse("admin_alerta_passagem_editar", args=[alerta.id]) if request.user.is_superuser else "#")
                ),
                "edit_url": reverse("admin_alerta_passagem_editar", args=[alerta.id]) if request.user.is_superuser else None,
                "delete_url": reverse("admin_alerta_passagem_deletar", args=[alerta.id]) if request.user.is_superuser else None,
                "classe_label": alerta.get_classe_display(),
                "milhas_label": f"{alerta.valor_milhas:,.0f}".replace(",", ".") if alerta.valor_milhas else "Nao informado",
            }
        )

    base_params = {
        "q": search_query,
        "programa": selected_programa,
        "classe": selected_classe,
        "continente": selected_continente,
        "pais": selected_pais,
        "cidade": selected_cidade,
    }

    status_chips = [
        {
            "label": "Ativos",
            "selected": selected_status == "ativos",
            "query": _query_with(base_params, status_alerta="ativos"),
        },
        {
            "label": "Favoritos",
            "selected": selected_status == "favoritos",
            "query": _query_with(base_params, status_alerta="favoritos"),
        },
        {
            "label": "Melhorando",
            "selected": selected_status == "melhorando",
            "query": _query_with(base_params, status_alerta="melhorando"),
        },
    ]

    return render(
        request,
        "admin_custom/alertas_list.html",
        {
            "alert_cards": alert_cards,
            "alerta_totais": {
                "ativos": sum(1 for item in alert_cards if item["alerta"].ativo),
                "melhorando": improving_count,
                "favoritos": favorites_count,
                "realizadas": resolved_count,
                "criticos": critical_count,
                "monitorado": len(alert_cards),
                "recentes": recent_count,
            },
            "continente_options": [
                {
                    "label": value,
                    "selected": value == selected_continente,
                    "query": _query_with(base_params, continente=value, pais=None, cidade=None, status_alerta=selected_status),
                }
                for value in continentes
            ],
            "pais_options": [
                {
                    "label": value,
                    "selected": value == selected_pais,
                    "query": _query_with(base_params, pais=value, cidade=None, status_alerta=selected_status),
                }
                for value in paises
            ],
            "cidade_options": [
                {
                    "label": value,
                    "selected": value == selected_cidade,
                    "query": _query_with(base_params, cidade=value, status_alerta=selected_status),
                }
                for value in cidades
            ],
            "programa_options": list(
                AlertaViagem.objects.order_by("programa_fidelidade")
                .values_list("programa_fidelidade", flat=True)
                .distinct()
            ),
            "selected_programa": selected_programa,
            "selected_classe": selected_classe,
            "selected_status": selected_status,
            "search_query": search_query,
            "status_chips": status_chips,
            "clear_destination_query": _query_with(base_params, continente=None, pais=None, cidade=None, status_alerta=selected_status),
            "clear_filters_query": _query_with({}, status_alerta="ativos"),
            "menu_ativo": "alertas",
        },
    )


@login_required
def criar_alerta_passagem(request):
    if permission_denied := _require_superuser(request):
        return permission_denied
    aeroportos_json = [
        serialize_airport_for_alerts(airport)
        for airport in Aeroporto.objects.order_by("id")
    ]
    if request.method == "POST":
        parsed = parse_alerta_bruto(request.POST.get("alerta_bruto", ""))
        post_data = backfill_alerta_post_data(request.POST, parsed)
        form = AlertaViagemForm(post_data)
        if "autopreencher" in request.POST:
            if parsed:
                messages.success(request, "Campos preenchidos a partir do alerta bruto. Revise e salve.")
            else:
                messages.warning(request, "Nao foi possivel interpretar o alerta bruto nesse formato.")
            return render(
                request,
                "admin_custom/alertas_form.html",
                {
                    "form": form,
                    "titulo_pagina": "Novo alerta",
                    "menu_ativo": "alertas",
                    "aeroportos_json": aeroportos_json,
                },
            )
        if form.is_valid():
            alerta, created = create_or_update_alerta(form.cleaned_data)
            sync_alerta_interest_matches(alerta)
            messages.success(
                request,
                "Alerta criado com sucesso." if created else "Alerta existente atualizado com novas datas e valores.",
            )
            return redirect("admin_alertas_passagens")
    else:
        form = AlertaViagemForm()
    return render(
        request,
        "admin_custom/alertas_form.html",
        {
            "form": form,
            "titulo_pagina": "Novo alerta",
            "menu_ativo": "alertas",
            "aeroportos_json": aeroportos_json,
        },
    )


@login_required
def editar_alerta_passagem(request, alerta_id):
    if permission_denied := _require_superuser(request):
        return permission_denied
    alerta = get_object_or_404(AlertaViagem, id=alerta_id)
    aeroportos_json = [
        serialize_airport_for_alerts(airport)
        for airport in Aeroporto.objects.order_by("id")
    ]
    if request.method == "POST":
        parsed = parse_alerta_bruto(request.POST.get("alerta_bruto", ""))
        post_data = backfill_alerta_post_data(request.POST, parsed)
        form = AlertaViagemForm(post_data, instance=alerta)
        if "autopreencher" in request.POST:
            if parsed:
                messages.success(request, "Campos preenchidos a partir do alerta bruto. Revise e salve.")
            else:
                messages.warning(request, "Nao foi possivel interpretar o alerta bruto nesse formato.")
            return render(
                request,
                "admin_custom/alertas_form.html",
                {
                    "form": form,
                    "titulo_pagina": "Editar alerta",
                    "menu_ativo": "alertas",
                    "aeroportos_json": aeroportos_json,
                },
            )
        if form.is_valid():
            alerta = form.save()
            sync_alerta_interest_matches(alerta)
            messages.success(request, "Alerta atualizado com sucesso.")
            return redirect("admin_alertas_passagens")
    else:
        form = AlertaViagemForm(instance=alerta)
    return render(
        request,
        "admin_custom/alertas_form.html",
        {
            "form": form,
            "titulo_pagina": "Editar alerta",
            "menu_ativo": "alertas",
            "aeroportos_json": aeroportos_json,
        },
    )


@login_required
def deletar_alerta_passagem(request, alerta_id):
    if permission_denied := _require_superuser(request):
        return permission_denied
    alerta = get_object_or_404(AlertaViagem, id=alerta_id)
    if request.method == "POST":
        alerta.delete()
        messages.success(request, "Alerta removido com sucesso.")
        return redirect("admin_alertas_passagens")
    return render(
        request,
        "admin_custom/alertas_confirm_delete.html",
        {"alerta": alerta, "menu_ativo": "alertas"},
    )


@login_required
def alertas_passagens(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    base_qs = _alertas_vitrine_queryset()
    continentes = list(base_qs.values_list("continente", flat=True).distinct().order_by("continente"))
    selected_continente = request.GET.get("continente") or None
    if selected_continente not in continentes:
        selected_continente = None
    paises = []
    if selected_continente:
        paises = list(
            base_qs.filter(continente=selected_continente)
            .values_list("pais", flat=True)
            .distinct()
            .order_by("pais")
        )
    selected_pais = request.GET.get("pais") or None
    if selected_pais not in paises:
        selected_pais = None
    cidades = []
    if selected_continente and selected_pais:
        cidades = list(
            base_qs.filter(continente=selected_continente, pais=selected_pais)
            .values_list("cidade_destino", flat=True)
            .distinct()
            .order_by("cidade_destino")
        )
    selected_cidade = request.GET.get("cidade") or None
    if selected_cidade not in cidades:
        selected_cidade = None
    alertas = base_qs
    if selected_continente:
        alertas = alertas.filter(continente=selected_continente)
    if selected_pais:
        alertas = alertas.filter(pais=selected_pais)
    if selected_cidade:
        alertas = alertas.filter(cidade_destino=selected_cidade)
    else:
        alertas = alertas.none()
    return render(
        request,
        "admin_custom/alertas_vitrine.html",
        {
            "alertas": alertas,
            "continentes": continentes,
            "paises": paises,
            "cidades": cidades,
            "selected_continente": selected_continente,
            "selected_pais": selected_pais,
            "selected_cidade": selected_cidade,
            "menu_ativo": "alertas",
        },
    )


@login_required
def alerta_passagem_detalhe(request, alerta_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    alerta = get_object_or_404(AlertaViagem, id=alerta_id, ativo=True)
    if not alerta.deve_aparecer_na_vitrine():
        raise Http404("Alerta nao disponivel.")
    return render(
        request,
        "admin_custom/alertas_detail.html",
        {
            "alerta": alerta,
            "datas_ida": alerta.datas_ida or [],
            "datas_volta": alerta.datas_volta or [],
            "link_externo": _extract_link(alerta.conteudo),
            "back_url": _resolve_alert_back_url(request),
            "menu_ativo": "alertas",
        },
    )


@csrf_exempt
def telegram_alertas_webhook(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    config = get_telegram_alertas_config()
    expected_secret = config["secret"]
    if expected_secret:
        received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if received_secret != expected_secret:
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    try:
        event, outcome = process_telegram_alert_update(payload)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "outcome": outcome,
            "event_id": event.id,
            "alerta_id": event.alerta_id,
        }
    )

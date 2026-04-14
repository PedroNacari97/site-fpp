import json
import logging
import os
import re
import threading
from datetime import date, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
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
    telegram_send_message,
)
from ..services.telegram_noticias import (
    get_telegram_noticias_config,
    looks_like_manual_news_text,
    parse_single_news_url_command,
    process_telegram_news_update,
    telegram_news_send_message,
)
from portal.services.alert_email_broadcasts import (
    capture_alert_email_snapshot,
    notify_alert_subscribers,
)
from .permissions import require_admin_or_operator

logger = logging.getLogger(__name__)


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
            previous_snapshot = capture_alert_email_snapshot(alerta)
            alerta = form.save()
            sync_alerta_interest_matches(alerta)
            notify_alert_subscribers(alerta, created=False, previous_snapshot=previous_snapshot)
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


_NEWS_COMMAND_RE = re.compile(r"^atualizar\s*(\d+)?$", re.IGNORECASE)


def _parse_news_command(text):
    match = _NEWS_COMMAND_RE.match((text or "").strip())
    if match:
        limit = int(match.group(1)) if match.group(1) else 10
        return max(1, min(limit, 50))
    return None


def _run_news_sync_background(news_limit, chat_id):
    """Executa o sync de notícias em background para não bloquear o webhook."""
    from portal.services.news_sync_service import sync_news_progressive
    from portal.views import invalidate_news_cache

    published_count = 0

    def _on_published(noticia):
        nonlocal published_count
        published_count += 1
        if chat_id:
            try:
                url = noticia.get_absolute_url()
                telegram_send_message(
                    chat_id,
                    f"✅ {published_count}. {noticia.titulo}\n{noticia.categoria}\nhttps://www.ncfly.com.br{url}"
                )
            except Exception:
                pass

    try:
        processed, published, errors = sync_news_progressive(limit=news_limit, on_published=_on_published)
        invalidate_news_cache()
        result = f"Sync concluído: {processed} processadas, {published} publicadas."
        if errors:
            result += f" ({len(errors)} erros)"
    except Exception as exc:
        result = f"Erro ao sincronizar: {exc}"

    if chat_id:
        try:
            telegram_send_message(chat_id, result)
        except Exception:
            pass


def _extract_chat_id(payload):
    msg = payload.get("message") or payload.get("channel_post") or {}
    return (msg.get("chat") or {}).get("id")


def _public_site_base_url(request=None):
    configured = str(getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if configured:
        return configured
    if request is not None:
        return request.build_absolute_uri("/").rstrip("/")
    return "https://ncfly.com.br"


def _build_telegram_alert_feedback(outcome, event, *, request=None):
    alerta = getattr(event, "alerta", None)
    route_label = ""
    if alerta:
        route_label = f"{alerta.origem} para {alerta.destino}".strip(" para ")
    alert_url = ""
    if alerta:
        alert_url = f"{_public_site_base_url(request)}{reverse('portal_alerta_detalhe', args=[alerta.id])}"

    if outcome == "created" and alerta:
        lines = [
            "Alerta publicado com sucesso.",
            f"Rota: {route_label}" if route_label else f"Alerta: {alerta.titulo}",
            f"Programa: {alerta.programa_fidelidade}" if alerta.programa_fidelidade else "",
            f"Ver no site: {alert_url}" if alert_url else "",
        ]
        return "\n".join([line for line in lines if line])

    if outcome == "updated" and alerta:
        lines = [
            "Alerta atualizado com sucesso.",
            f"Rota: {route_label}" if route_label else f"Alerta: {alerta.titulo}",
            f"Programa: {alerta.programa_fidelidade}" if alerta.programa_fidelidade else "",
            f"Ver no site: {alert_url}" if alert_url else "",
        ]
        return "\n".join([line for line in lines if line])

    if outcome == "duplicate_update":
        return "Esse update do Telegram ja foi processado antes."
    if outcome == "ignored_chat":
        return "Esse chat nao esta autorizado para cadastrar alertas."
    if outcome == "ignored_empty":
        return "Nao encontrei texto util para interpretar o alerta."
    if outcome == "ignored_duplicate_message":
        return "Essa mensagem ja tinha sido processada antes."
    if outcome == "parse_error":
        error_detail = getattr(event, "erro", "") or "Nao consegui interpretar o alerta nesse formato."
        return f"Nao consegui interpretar o alerta.\n{error_detail}"
    return "O alerta foi recebido, mas nao foi possivel determinar o resultado."


def _run_telegram_news_update_background(payload, chat_id):
    published_count = 0

    def _on_news_published(noticia):
        nonlocal published_count
        published_count += 1

        # Publicar no Instagram automaticamente
        try:
            from gestao.services.instagram_publisher import is_instagram_configured, publish_noticia_to_instagram
            if is_instagram_configured():
                publish_noticia_to_instagram(noticia)
        except Exception:
            pass

        if not chat_id:
            return
        try:
            url = noticia.get_absolute_url()
            evento_ig = noticia.instagram_eventos.filter(status="publicado").order_by("-criado_em").first()
            ig_status = "Instagram: publicado" if evento_ig else "Instagram: nao publicado"
            telegram_news_send_message(
                chat_id,
                f"{published_count}. {noticia.titulo}\n{noticia.categoria}\nhttps://www.ncfly.com.br{url}\n{ig_status}",
            )
        except Exception:
            pass

    try:
        event, outcome, meta = process_telegram_news_update(payload, on_published=_on_news_published)
        message = meta.get("message")
        if not message and outcome == "ignored_unknown_format":
            message = "Formato nao suportado. Envie 'atualizar 10', um link ou um texto promocional."
        elif not message and outcome == "ignored_chat":
            message = "Esse chat nao esta autorizado para o bot de noticias."
        elif not message and outcome == "ignored_duplicate_message":
            message = "Essa mensagem ja foi processada antes."
        elif not message and outcome == "ignored_empty":
            message = "Nao encontrei texto util para processar."
        elif not message and outcome == "processing_error":
            message = "Ocorreu um erro ao processar sua solicitacao."

        target_chat_id = event.chat_id or chat_id
        if target_chat_id and message:
            telegram_news_send_message(target_chat_id, message)
    except Exception as exc:
        if chat_id:
            try:
                telegram_news_send_message(chat_id, f"Erro ao processar noticia: {exc}")
            except Exception:
                pass


def _build_telegram_news_acknowledgement(raw_text):
    clean_text = (raw_text or "").strip()
    news_limit = _parse_news_command(clean_text)
    if news_limit is not None:
        return (
            f"Recebi o comando atualizar {news_limit}.\n"
            "Vou buscar as noticias agora e te devolver um resumo quando terminar."
        )

    if parse_single_news_url_command(clean_text):
        return (
            "Recebi o link.\n"
            "Vou analisar a materia, comparar com o que ja existe e te responder aqui."
        )

    if looks_like_manual_news_text(clean_text):
        return (
            "Recebi o texto da noticia.\n"
            "Vou montar a materia e tentar gerar a capa automaticamente. Isso pode levar um pouco mais."
        )

    return ""


@login_required
def admin_configurar_telegram_webhook(request):
    if not request.user.is_superuser:
        return render(request, "sem_permissao.html", status=403)

    from django.conf import settings
    from ..services.telegram_alertas import telegram_set_webhook

    base_url = (getattr(settings, "SITE_BASE_URL", "") or request.build_absolute_uri("/").rstrip("/"))
    webhook_url = f"{base_url}/integracoes/telegram/alertas/webhook/"

    if request.method == "POST":
        try:
            telegram_set_webhook(webhook_url)
            messages.success(request, f"Webhook configurado com sucesso: {webhook_url}")
        except Exception as exc:
            messages.error(request, f"Erro ao configurar webhook: {exc}")
        return redirect("admin_configurar_telegram_webhook")

    return render(request, "admin_custom/telegram_webhook.html", {
        "webhook_url": webhook_url,
        "menu_ativo": "alertas",
    })


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

    chat_id = _extract_chat_id(payload)

    try:
        event, outcome = process_telegram_alert_update(payload)
    except Exception as exc:
        if chat_id:
            try:
                telegram_send_message(chat_id, f"Erro ao processar alerta: {exc}")
            except Exception:
                logger.exception("Falha ao enviar mensagem de erro do bot de alertas.")
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    feedback_message = _build_telegram_alert_feedback(outcome, event, request=request)
    if chat_id and feedback_message:
        try:
            telegram_send_message(chat_id, feedback_message)
        except Exception:
            logger.exception("Falha ao enviar retorno do bot de alertas.")

    return JsonResponse(
        {
            "ok": True,
            "outcome": outcome,
            "event_id": event.id,
            "alerta_id": event.alerta_id,
        }
    )


@csrf_exempt
def telegram_noticias_webhook(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    config = get_telegram_noticias_config()
    expected_secret = config["secret"]
    if expected_secret:
        received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if received_secret != expected_secret:
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    chat_id = _extract_chat_id(payload)
    msg = payload.get("message") or payload.get("channel_post") or {}
    raw_text = (msg.get("text") or msg.get("caption") or "").strip()
    ack_message = _build_telegram_news_acknowledgement(raw_text)
    if chat_id and ack_message:
        try:
            telegram_news_send_message(chat_id, ack_message)
        except Exception:
            logger.exception("Falha ao enviar confirmacao imediata do bot de noticias.")

    thread = threading.Thread(
        target=_run_telegram_news_update_background,
        args=(payload, chat_id),
        daemon=True,
    )
    thread.start()

    return JsonResponse({"ok": True, "outcome": "news_processing_started"})


# ---------------------------------------------------------------------------
# Webhook de artigos via Telegram — processa texto longo com IA e salva draft
# ---------------------------------------------------------------------------

_TELEGRAM_ARTIGOS_SECRET = os.environ.get("TELEGRAM_ARTIGOS_SECRET", "")
_ARTIGO_MIN_CHARS = 200


def _telegram_artigos_send_message(chat_id, text):
    """Envia mensagem de texto para um chat via Telegram Bot API."""
    bot_token = os.environ.get("TELEGRAM_ARTIGOS_BOT_TOKEN", "")
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urlopen(req, timeout=10)
    except Exception:
        logger.exception("Falha ao enviar mensagem pelo bot de artigos Telegram.")


def _run_artigo_pipeline_background(raw_text, chat_id):
    """Chama o pipeline de IA, salva o rascunho e notifica o remetente."""
    from portal.services.ai_pipeline import build_news_draft
    from portal.models import NoticiaPublicada

    try:
        raw_article = {
            "titulo_extraido": raw_text[:220],
            "texto_base": raw_text,
            "url_original": "",
            "imagem_url": "",
        }
        draft = build_news_draft("telegram_artigos", raw_article)

        noticia = NoticiaPublicada(
            titulo=draft.titulo,
            resumo=draft.resumo,
            conteudo=draft.conteudo,
            categoria=draft.categoria,
            topico=draft.topico,
            tags_json=draft.tags,
            imagem_url=draft.imagem_url,
            imagem_ilustrativa=draft.imagem_ilustrativa,
            url_fonte="",
            status="published",
            confianca=draft.confianca,
            metadata_json={
                **(draft.metadata or {}),
                "origem": "telegram_artigos",
                "seo_title": draft.seo_title,
                "meta_description": draft.meta_description,
                "cta_url": draft.cta_url,
                "cta_label": draft.cta_label,
                "imagem_prompt": draft.imagem_prompt,
            },
        )
        noticia.save()

        mensagem = (
            f"Artigo publicado com sucesso!\n"
            f"Titulo: {noticia.titulo}\n"
            f"Categoria: {noticia.categoria}\n"
            f"URL: /home/artigos/"
        )
        _telegram_artigos_send_message(chat_id, mensagem)
        logger.info("telegram_artigos_webhook: artigo publicado %s (id=%s).", noticia.titulo, noticia.id)

    except Exception as exc:
        logger.exception("telegram_artigos_webhook: erro no pipeline de IA.")
        _telegram_artigos_send_message(chat_id, f"Erro ao processar o artigo: {exc}")


@csrf_exempt
def telegram_artigos_webhook(request):
    """Recebe artigos via Telegram, processa com IA e salva como rascunho."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    expected_secret = _TELEGRAM_ARTIGOS_SECRET
    if expected_secret:
        received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if received_secret != expected_secret:
            logger.warning("telegram_artigos_webhook: secret invalido recebido.")
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    chat_id = _extract_chat_id(payload)
    msg = payload.get("message") or payload.get("channel_post") or {}
    raw_text = (msg.get("text") or msg.get("caption") or "").strip()

    if len(raw_text) < _ARTIGO_MIN_CHARS:
        logger.info(
            "telegram_artigos_webhook: mensagem muito curta (%d chars), ignorada.",
            len(raw_text),
        )
        if chat_id:
            _telegram_artigos_send_message(
                chat_id,
                f"Mensagem muito curta. Envie um artigo com pelo menos {_ARTIGO_MIN_CHARS} caracteres.",
            )
        return JsonResponse({"ok": False, "error": "text_too_short"}, status=200)

    if chat_id:
        try:
            _telegram_artigos_send_message(
                chat_id,
                "Recebi o artigo. Estou processando com IA e vou salvar o rascunho em instantes.",
            )
        except Exception:
            logger.exception("telegram_artigos_webhook: falha ao enviar confirmacao imediata.")

    thread = threading.Thread(
        target=_run_artigo_pipeline_background,
        args=(raw_text, chat_id),
        daemon=True,
    )
    thread.start()

    return JsonResponse({"ok": True, "outcome": "artigo_processing_started"})

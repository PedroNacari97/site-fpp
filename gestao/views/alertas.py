import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q

from ..forms import AlertaViagemForm
from ..models import AlertaViagem
from .permissions import require_admin_or_operator
from gestao.services.dashboard import (
    _current_management_filters,
    _management_filter_list,
    _management_filter_value,
    build_operational_dashboard_context,
)


def _require_superuser(request):
    if not request.user.is_superuser:
        return render(request, "sem_permissao.html")
    return None


def _extract_link(conteudo):
    if not conteudo:
        return None
    match = re.search(r"(https?://\\S+)", conteudo)
    return match.group(1) if match else None


@login_required
def admin_alertas_passagens(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    management_context = build_operational_dashboard_context(user=request.user, request=request)
    management_dashboard = management_context["management_dashboard"]
    active_filters = _current_management_filters(request)
    start_date = _management_filter_value(active_filters, "data_inicio")
    end_date = _management_filter_value(active_filters, "data_fim")
    selected_status = _management_filter_value(active_filters, "status")
    selected_clientes = _management_filter_list(active_filters, "cliente")
    selected_programas = _management_filter_list(active_filters, "programa")

    alertas = AlertaViagem.objects.all()
    if start_date:
        alertas = alertas.filter(criado_em__date__gte=start_date)
    if end_date:
        alertas = alertas.filter(criado_em__date__lte=end_date)
    if selected_status == "pendente":
        alertas = alertas.filter(ativo=True)
    elif selected_status == "emitido":
        alertas = alertas.filter(ativo=False)
    if selected_programas:
        programas = management_dashboard.get("filter_options", {}).get("programas", [])
        allowed_program_names = {
            item["label"]
            for item in programas
            if str(item.get("id")) in {str(pid) for pid in selected_programas}
        }
        if allowed_program_names:
            alertas = alertas.filter(programa_fidelidade__in=allowed_program_names)
    if selected_clientes:
        clientes = management_dashboard.get("filter_options", {}).get("clientes", [])
        allowed_client_names = {
            item["label"]
            for item in clientes
            if str(item.get("id")) in {str(cid) for cid in selected_clientes}
        }
        if allowed_client_names:
            alertas = alertas.filter(titulo__iregex=r"(" + "|".join(map(re.escape, allowed_client_names)) + r")")

    alertas = alertas.order_by("-criado_em")
    alertas_rows = []
    criticos_count = 0
    for alerta in alertas:
        conteudo = (alerta.conteudo or "").lower()
        titulo = (alerta.titulo or "").lower()
        is_critico = "crític" in conteudo or "urgente" in conteudo or "crític" in titulo
        if is_critico and alerta.ativo:
            status_label = "🔴 crítico"
            criticos_count += 1
        elif alerta.ativo:
            status_label = "🟡 atenção"
        else:
            status_label = "🟢 resolvido"
        alertas_rows.append({"alerta": alerta, "status_label": status_label})

    alertas_ativos = sum(1 for item in alertas_rows if item["alerta"].ativo)
    alertas_resolvidos = sum(1 for item in alertas_rows if not item["alerta"].ativo)
    total_monitorado = len(alertas_rows)
    return render(
        request,
        "admin_custom/alertas_list.html",
        {
            "alertas_rows": alertas_rows,
            "alerta_totais": {
                "ativos": alertas_ativos,
                "resolvidos": alertas_resolvidos,
                "criticos": criticos_count,
                "monitorado": total_monitorado,
            },
            "management_dashboard": management_dashboard,
            "menu_ativo": "alertas",
        },
    )


@login_required
def criar_alerta_passagem(request):
    if permission_denied := _require_superuser(request):
        return permission_denied
    if request.method == "POST":
        form = AlertaViagemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Alerta criado com sucesso.")
            return redirect("admin_alertas_passagens")
    else:
        form = AlertaViagemForm()
    return render(
        request,
        "admin_custom/alertas_form.html",
        {"form": form, "titulo_pagina": "Novo alerta", "menu_ativo": "alertas"},
    )


@login_required
def editar_alerta_passagem(request, alerta_id):
    if permission_denied := _require_superuser(request):
        return permission_denied
    alerta = get_object_or_404(AlertaViagem, id=alerta_id)
    if request.method == "POST":
        form = AlertaViagemForm(request.POST, instance=alerta)
        if form.is_valid():
            form.save()
            messages.success(request, "Alerta atualizado com sucesso.")
            return redirect("admin_alertas_passagens")
    else:
        form = AlertaViagemForm(instance=alerta)
    return render(
        request,
        "admin_custom/alertas_form.html",
        {"form": form, "titulo_pagina": "Editar alerta", "menu_ativo": "alertas"},
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
    base_qs = AlertaViagem.objects.filter(ativo=True)
    continentes = list(
        base_qs.values_list("continente", flat=True)
        .distinct()
        .order_by("continente")
    )
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
    return render(
        request,
        "admin_custom/alertas_detail.html",
        {
            "alerta": alerta,
            "datas_ida": alerta.datas_ida or [],
            "datas_volta": alerta.datas_volta or [],
            "link_externo": _extract_link(alerta.conteudo),
            "menu_ativo": "alertas",
        },
    )

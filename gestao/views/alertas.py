import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q

from ..forms import AlertaViagemForm
from ..models import AlertaViagem
from .permissions import require_admin_or_operator


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
    if permission_denied := _require_superuser(request):
        return permission_denied
    busca = request.GET.get("busca", "").strip()
    alertas = AlertaViagem.objects.all()
    if busca:
        alertas = alertas.filter(
            Q(titulo__icontains=busca)
            | Q(continente__icontains=busca)
            | Q(pais__icontains=busca)
            | Q(cidade_destino__icontains=busca)
        )
    return render(
        request,
        "admin_custom/alertas_list.html",
        {"alertas": alertas, "busca": busca, "menu_ativo": "alertas"},
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

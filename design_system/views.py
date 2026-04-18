"""Rotas de PREVIEW do design system NCfly.

Estas views renderizam os mockups do redesign como paginas estaticas
clicaveis em /design/. Sao totalmente isoladas dos apps reais
(portal, painel_cliente, gestao, accounts, superadmin, onboarding).

SEM autenticacao intencionalmente — o objetivo e permitir que o time de
produto abra http://localhost:8000/design/ e navegue pelos mockups. Em
producao, o ideal e remover o include de design_system/urls.py ou
proteger com middleware de staging.
"""

from django.shortcuts import render


def index(request):
    return render(request, "ds/index.html")


def components(request):
    return render(request, "ds/components.html")


def login(request):
    return render(request, "ds/login.html")


def admin_dashboard(request):
    return render(request, "ds/admin_dashboard.html")


def admin_clientes(request):
    return render(request, "ds/admin_clientes.html")


def admin_emissoes(request):
    return render(request, "ds/admin_emissoes.html")


def admin_contas(request):
    return render(request, "ds/admin_contas.html")


def painel_cliente(request):
    return render(request, "ds/painel_cliente.html")


def cotar_emitir(request):
    return render(request, "ds/cotar_emitir.html")


def transferencia(request):
    return render(request, "ds/transferencia.html")


def onboarding(request):
    return render(request, "ds/onboarding.html")


def portal(request):
    return render(request, "ds/portal.html")


def admin_cadastros(request):
    return render(request, "ds/admin_cadastros.html")


def admin_form_cliente(request):
    return render(request, "ds/admin_form_cliente.html")


def admin_formularios(request):
    return render(request, "ds/admin_formularios.html")


def admin_movimentacoes(request):
    return render(request, "ds/admin_movimentacoes.html")


def cliente_consolidado(request):
    return render(request, "ds/cliente_consolidado.html")

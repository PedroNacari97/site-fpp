"""URLs de PREVIEW do design system — prefixo /design/ em core/urls.py."""

from django.urls import path

from . import views

app_name = "design_system"

urlpatterns = [
    path("", views.index, name="index"),
    path("components/", views.components, name="components"),
    path("login/", views.login, name="login"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-clientes/", views.admin_clientes, name="admin_clientes"),
    path("admin-emissoes/", views.admin_emissoes, name="admin_emissoes"),
    path("admin-contas/", views.admin_contas, name="admin_contas"),
    path("painel-cliente/", views.painel_cliente, name="painel_cliente"),
    path("cotar-emitir/", views.cotar_emitir, name="cotar_emitir"),
    path("transferencia/", views.transferencia, name="transferencia"),
    path("onboarding/", views.onboarding, name="onboarding"),
    path("portal/", views.portal, name="portal"),
    path("admin-cadastros/", views.admin_cadastros, name="admin_cadastros"),
    path("admin-form-cliente/", views.admin_form_cliente, name="admin_form_cliente"),
    path("admin-formularios/", views.admin_formularios, name="admin_formularios"),
    path("admin-movimentacoes/", views.admin_movimentacoes, name="admin_movimentacoes"),
    path("cliente-consolidado/", views.cliente_consolidado, name="cliente_consolidado"),
]

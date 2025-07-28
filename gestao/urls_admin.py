from django.urls import path
from .views_admin import (
    admin_dashboard,
    admin_clientes,
    admin_contas,
    admin_cotacoes,
    admin_emissoes,
    criar_conta,   # <-- Adiciona aqui!
)


urlpatterns = [
    path('painel/', admin_dashboard, name='admin_dashboard'),
    path('clientes/', admin_clientes, name='admin_clientes'),
    path('contas/', admin_contas, name='admin_contas'),
    path('cotacoes/', admin_cotacoes, name='admin_cotacoes'),
    path('emissoes/', admin_emissoes, name='admin_emissoes'),
    path('contas/novo/', criar_conta, name='admin_nova_conta'),
]

from django.urls import path
from .views_admin import (
    admin_dashboard,
    admin_clientes,
    admin_contas,
    admin_emissoes,
    criar_conta,   # <-- Adiciona aqui!
    admin_programas,
    editar_programa,
    criar_cliente,
    editar_cliente,
    admin_aeroportos,
    editar_aeroporto,
)


urlpatterns = [
    path('painel/', admin_dashboard, name='admin_dashboard'),
    path('clientes/', admin_clientes, name='admin_clientes'),
    path('clientes/<int:cliente_id>/editar/', editar_cliente, name='admin_editar_cliente'),
    path('contas/', admin_contas, name='admin_contas'),
    path('programas/', admin_programas, name='admin_programas'),
    path('programas/<int:programa_id>/editar/', editar_programa, name='admin_editar_programa'),
    path('aeroportos/', admin_aeroportos, name='admin_aeroportos'),
    path('aeroportos/<int:aeroporto_id>/editar/', editar_aeroporto, name='admin_editar_aeroporto'),
    path('emissoes/', admin_emissoes, name='admin_emissoes'),
    path('contas/novo/', criar_conta, name='admin_nova_conta'),
    path('clientes/novo/', criar_cliente, name='admin_novo_cliente'),
]
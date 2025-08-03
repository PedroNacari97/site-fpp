from django.urls import path
from .views import (
    empresa_list,
    empresa_create,
    administrador_create,
    operador_create,
    cliente_create,
    administrador_list,
    toggle_admin,
)

urlpatterns = [
    path("empresas/", empresa_list, name="superadmin_empresa_list"),
    path("empresas/nova/", empresa_create, name="superadmin_empresa_create"),
    path("administradores/novo/", administrador_create, name="superadmin_administrador_create"),
    path("operadores/novo/", operador_create, name="superadmin_operador_create"),
    path("clientes/novo/", cliente_create, name="superadmin_cliente_create"),
    path("administradores/", administrador_list, name="superadmin_administrador_list"),
    path("administradores/<int:admin_id>/toggle/", toggle_admin, name="superadmin_toggle_admin"),
]


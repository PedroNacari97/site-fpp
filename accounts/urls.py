from django.urls import path
from django.views.generic import RedirectView

from .views import (
    cliente_create,
    operator_list,
    password_help,
    user_create,
    user_delete,
    user_edit,
    user_list,
)

urlpatterns = [
    path("login/", RedirectView.as_view(pattern_name="login_custom", permanent=False), name="login_legacy"),
    path("login/ajuda-senha/", password_help, name="password_help"),
    path("usuarios/", user_list, name="user_list"),
    path("usuarios/operadores/", operator_list, name="operator_list"),
    path("usuarios/novo/", user_create, name="user_create"),
    path("usuarios/<int:user_id>/editar/", user_edit, name="user_edit"),
    path("usuarios/<int:user_id>/excluir/", user_delete, name="user_delete"),
    path("cliente/novo/", cliente_create, name="cliente_create"),
]

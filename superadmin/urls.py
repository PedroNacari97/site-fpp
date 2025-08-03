from django.urls import path
from . import views

urlpatterns = [
    path("empresas/", views.empresa_list, name="superadmin_empresa_list"),
    path("empresas/nova/", views.empresa_create, name="superadmin_empresa_create"),
    path("administradores/novo/", views.administrador_create, name="superadmin_administrador_create"),
]

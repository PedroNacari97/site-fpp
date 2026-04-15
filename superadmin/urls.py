"""
URLs do painel superadmin NCfly.

Path base: /ncadm/   (registrado em core/urls.py)
"""
from django.urls import path

from . import views

urlpatterns = [
    # Dashboard
    path("", views.DashboardView.as_view(), name="superadmin_dashboard"),

    # Noticias
    path("noticias/", views.NoticiasListView.as_view(), name="superadmin_noticias_list"),
    path("noticias/<int:pk>/excluir/", views.NoticiaDeleteView.as_view(), name="superadmin_noticia_delete"),
    path("noticias/upload/", views.ArtigoUploadView.as_view(), name="superadmin_artigo_upload"),

    # Empresas
    path("empresas/", views.EmpresasListView.as_view(), name="superadmin_empresas_list"),
    path("empresas/nova/", views.EmpresaCreateView.as_view(), name="superadmin_empresa_create"),
    path("empresas/<int:pk>/", views.EmpresaDetailView.as_view(), name="superadmin_empresa_detail"),
    path("empresas/<int:pk>/editar/", views.EmpresaEditView.as_view(), name="superadmin_empresa_edit"),
]

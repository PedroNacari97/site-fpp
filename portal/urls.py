from django.urls import path

from . import views


urlpatterns = [
    path("", views.home_publica, name="portal_home"),
    path("categorias/<slug:categoria_slug>/", views.categoria_lista, name="portal_categoria"),
    path("noticias/<slug:slug>/", views.noticia_detalhe, name="portal_noticia_detalhe"),
]

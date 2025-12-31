from django.urls import path, re_path
from gestao.views import (
    api_cards,
    api_dashboard,
    api_emissoes,
    cotacao_voo_pdf,
    emissao_detalhe,
    emissao_pdf,
)
from gestao.views.nuxt import api_me, gestao_nuxt

urlpatterns = [
    path("api/dashboard/", api_dashboard, name="api_dashboard"),
    path("api/cards/", api_cards, name="api_cards"),
    path("api/emissoes/", api_emissoes, name="api_emissoes"),
    path("api/me/", api_me, name="api_me"),
    path('cotacoes-voo/<int:cotacao_id>/pdf/', cotacao_voo_pdf, name='admin_cotacao_voo_pdf'),
    path('emissoes/<int:emissao_id>/pdf/', emissao_pdf, name='admin_emissao_pdf'),
    path('emissoes/<int:emissao_id>/detalhe/', emissao_detalhe, name='admin_emissao_detalhe'),
    re_path(r'^(?P<path>.*)$', gestao_nuxt, name='gestao_nuxt'),
]

from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="painel_dashboard"),  
    path("logout/", views.sair, name="logout"),
    path("parceiro/", views.parceiro_dashboard, name="painel_parceiro_dashboard"),
    path("parceiro/movimentacoes/", views.parceiro_movimentacoes, name="painel_parceiro_movimentacoes"),
    path("emissoes/", views.painel_emissoes, name="painel_emissoes"),
    path("emissoes/<int:emissao_id>/pdf/", views.emissao_pdf, name="emissao_pdf"),
    path("hoteis/", views.painel_hoteis, name="painel_hoteis"),
    path("movimentacoes/<int:conta_id>/", views.movimentacoes_programa, name="movimentacoes_programa"),
]

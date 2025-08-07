from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_custom_view, name='login_custom'),        # login
    path('dashboard/', views.dashboard, name='painel_dashboard'),  # dashboard cliente
    path('logout/', views.sair, name='logout'),
    path('emissoes/', views.painel_emissoes, name='painel_emissoes'),
    path('emissoes/<int:emissao_id>/pdf/', views.emissao_pdf, name='emissao_pdf'),
    path('hoteis/', views.painel_hoteis, name='painel_hoteis'),
    path('movimentacoes/<int:conta_id>/', views.movimentacoes_programa, name='movimentacoes_programa'),
]

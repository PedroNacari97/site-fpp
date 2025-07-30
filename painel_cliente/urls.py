from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_custom_view, name='login_custom'),
    path('logout/', views.sair, name='logout'),
    path('', views.dashboard, name='painel_dashboard'),
    path('emissoes/', views.painel_emissoes, name='painel_emissoes'),
    path('hoteis/', views.painel_hoteis, name='painel_hoteis'),
    path('movimentacoes/<int:conta_id>/', views.movimentacoes_programa, name='movimentacoes_programa'),
]

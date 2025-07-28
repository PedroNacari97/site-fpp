from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_custom_view, name='login_custom'),
    path('logout/', views.logout_view, name='logout'),
    path('painel/', views.painel_dashboard, name='painel_dashboard'),
    path('painel/emissoes/', views.painel_emissoes, name='painel_emissoes'),
    path('painel/movimentacoes/', views.painel_movimentacoes, name='painel_movimentacoes'),
]

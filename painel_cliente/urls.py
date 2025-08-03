from django.urls import path
from django.contrib.auth.views import LogoutView
from accounts.views import UserLoginView
from . import views

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login_custom'),
    path('logout/', LogoutView.as_view(next_page='login_custom'), name='logout'),
    path('', views.dashboard_view, name='painel_dashboard'),
    path('emissoes/', views.list_flight_emissions, name='painel_emissoes'),
    path('emissoes/<int:emissao_id>/pdf/', views.download_emission_pdf, name='emissao_pdf'),
    path('hoteis/', views.list_hotel_emissions, name='painel_hoteis'),
    path('movimentacoes/<int:conta_id>/', views.list_account_movements, name='movimentacoes_programa'),
]

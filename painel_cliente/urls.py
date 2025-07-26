from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='painel_dashboard'),
    path('emissoes/', views.emissoes, name='painel_emissoes'),
]

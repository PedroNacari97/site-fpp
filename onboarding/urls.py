from django.urls import path
from . import views

urlpatterns = [
    path("", views.landing, name="onboarding_landing"),
    path("conta/", views.step1, name="onboarding_step1"),
    path("empresa/", views.step2, name="onboarding_step2"),
    path("contrato/", views.step3, name="onboarding_step3"),
    path("plano/", views.step4, name="onboarding_step4"),
    path("bem-vindo/", views.welcome, name="onboarding_welcome"),
]

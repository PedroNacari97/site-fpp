"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from gestao import views

urlpatterns = [
    path('admin/', admin.site.urls),          # Django admin padrão
    path('adm/', include('gestao.urls_admin')),  # Painel admin customizado
    path('api/dashboard', views.api_dashboard, name='api_dashboard'),
    path('', include('painel_cliente.urls')),    # Painel do cliente comum
    path('adm/programas/', views.admin_programas, name='admin_programas'),
    path('adm/valor-milheiro/', views.admin_valor_milheiro, name='admin_valor_milheiro'),
    path('accounts/', include('accounts.urls')),
    path('superadmin/', include('superadmin.urls')),
]




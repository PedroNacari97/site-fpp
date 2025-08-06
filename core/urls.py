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
from painel_cliente.views import login_view  # ⬅ importa a view do login

urlpatterns = [
    path('', login_view, name='home'),                 # ⬅ página inicial = seu login
    path('admin/', admin.site.urls),                   # Django admin
    path('adm/', include('gestao.urls_admin')),        # Painel admin customizado
    path('api/dashboard', include('gestao.urls')),     # se tiver urls; se for só view, mantenha como estava
    path('', include('painel_cliente.urls')),          # demais rotas do painel do cliente
    path('adm/programas/', include('gestao.urls')),    # idem observação acima
    path('accounts/', include('accounts.urls')),
]



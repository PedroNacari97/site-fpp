from django.urls import path
from .views import custom_login, user_list, user_create, cliente_create

urlpatterns = [
    path('login/', custom_login, name='login_custom'),  # <<< ajuste aqui
    path('usuarios/', user_list, name='user_list'),
    path('usuarios/novo/', user_create, name='user_create'),
    path('cliente/novo/', cliente_create, name='cliente_create'),
]

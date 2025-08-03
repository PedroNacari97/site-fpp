from django.urls import path
from .views import custom_login, user_list, user_create, user_delete, cliente_create

urlpatterns = [
    path('login/', custom_login, name='login'),
    path('usuarios/', user_list, name='user_list'),
    path('usuarios/novo/', user_create, name='user_create'),
    path('usuarios/<int:user_id>/deletar/', user_delete, name='user_delete'),
    path('cliente/novo/', cliente_create, name='cliente_create'),
]

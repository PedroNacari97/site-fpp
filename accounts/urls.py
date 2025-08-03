from django.urls import path
from .views import UserLoginView, list_users, create_user, register_client

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('usuarios/', list_users, name='user_list'),
    path('usuarios/novo/', create_user, name='user_create'),
    path('cliente/novo/', register_client, name='cliente_create'),
]

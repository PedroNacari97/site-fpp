from django.db import models
from django.contrib.auth.models import User
from .cliente import Cliente

class AcessoClienteLog(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    data_acesso = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.admin} -> {self.cliente} em {self.data_acesso:%d/%m/%Y %H:%M}"

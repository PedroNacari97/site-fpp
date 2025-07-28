from django.db import models
from django.contrib.auth.models import User

class ContaFidelidade(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cliente_painel')
    saldo = models.DecimalField(max_digits=10, decimal_places=2, default=0)

class Cliente(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    # outros campos

class EmissaoPassagem(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    valor_referencia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # outros campos


# Create your models here.

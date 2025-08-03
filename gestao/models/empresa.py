from django.db import models


class Empresa(models.Model):
    nome = models.CharField(max_length=150)
    limite_administradores = models.PositiveIntegerField(default=0)
    limite_operadores = models.PositiveIntegerField(default=0)
    limite_clientes = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nome

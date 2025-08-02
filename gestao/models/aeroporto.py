from django.db import models

class Aeroporto(models.Model):
    nome = models.CharField(max_length=200)
    sigla = models.CharField(max_length=10)
    cidade = models.CharField(max_length=200)
    estado = models.CharField(max_length=100)

    class Meta:
        ordering = ["sigla"]

    def __str__(self):
        return f"{self.sigla} - {self.nome}"

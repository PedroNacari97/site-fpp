from django.db import models

class ProgramaFidelidade(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    preco_medio_milheiro = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    def __str__(self):
        return self.nome

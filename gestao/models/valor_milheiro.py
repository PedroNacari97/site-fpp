from django.db import models

class ValorMilheiro(models.Model):
    programa_nome = models.CharField(max_length=50, unique=True)
    valor_mercado = models.DecimalField(
        max_digits=8, decimal_places=2
    )  # Exemplo: 37.50
    atualizado_em = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.programa_nome} (R$ {self.valor_mercado})"

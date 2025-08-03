from django.db import models
from .emissao_passagem import EmissaoPassagem


class Passageiro(models.Model):
    CATEGORIA_CHOICES = (
        ("adulto", "Adulto"),
        ("crianca", "Criança"),
        ("bebe", "Bebê"),
    )

    emissao = models.ForeignKey(
        EmissaoPassagem, related_name="passageiros", on_delete=models.CASCADE
    )
    nome = models.CharField(max_length=150)
    documento = models.CharField(max_length=100)
    categoria = models.CharField(max_length=10, choices=CATEGORIA_CHOICES)

    def __str__(self):
        return f"{self.nome} ({self.get_categoria_display()})"

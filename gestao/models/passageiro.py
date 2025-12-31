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
    cpf = models.CharField(max_length=14)
    rg = models.CharField(max_length=50, blank=True)
    passaporte = models.CharField(max_length=30, blank=True)
    passaporte_validade = models.DateField(null=True, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    categoria = models.CharField(max_length=10, choices=CATEGORIA_CHOICES)

    def __str__(self):
        return f"{self.nome} ({self.get_categoria_display()})"

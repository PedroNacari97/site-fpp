from django.db import models

from .cliente import Cliente
from .passageiro_frequente import PassageiroFrequente


class CartaoCliente(models.Model):
    BANDEIRA_CHOICES = (
        ("visa", "Visa"),
        ("mastercard", "Mastercard"),
        ("elo", "Elo"),
        ("amex", "American Express"),
        ("hipercard", "Hipercard"),
        ("diners", "Diners Club"),
        ("discover", "Discover"),
        ("outro", "Outro"),
    )

    CATEGORIA_CHOICES = (
        ("standard", "Standard"),
        ("gold", "Gold"),
        ("platinum", "Platinum"),
        ("black", "Black"),
        ("infinite", "Infinite"),
        ("signature", "Signature"),
        ("nanquim", "Nanquim"),
        ("ultravioleta", "Ultravioleta"),
        ("the_one", "The One"),
        ("centurion", "Centurion"),
        ("outro", "Outro"),
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="cartoes",
    )
    passageiro_frequente = models.ForeignKey(
        PassageiroFrequente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cartoes",
        help_text="Se o cartao pertence a um passageiro frequente do cliente.",
    )
    bandeira = models.CharField(max_length=20, choices=BANDEIRA_CHOICES)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    banco = models.CharField(max_length=100)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cartao do Cliente"
        verbose_name_plural = "Cartoes dos Clientes"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["cliente"]),
        ]

    def __str__(self):
        titular = self.passageiro_frequente or self.cliente
        return f"{self.get_bandeira_display()} {self.get_categoria_display()} - {self.banco} ({titular})"


class ProgramaSalaVip(models.Model):
    cartao = models.ForeignKey(
        CartaoCliente,
        on_delete=models.CASCADE,
        related_name="programas_sala_vip",
    )
    nome = models.CharField(
        max_length=150,
        help_text="Ex: Dragon Pass, LoungeKey, Priority Pass, Plaza Premium",
    )
    acessos_titular = models.IntegerField(
        default=0,
        help_text="Numero de acessos para o titular. -1 = ilimitado.",
    )
    acessos_convidados = models.IntegerField(
        default=0,
        help_text="Numero de acessos para convidados. -1 = ilimitado.",
    )
    observacoes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Programa de Sala VIP"
        verbose_name_plural = "Programas de Sala VIP"
        ordering = ["nome"]

    @property
    def acessos_titular_display(self):
        return "Ilimitado" if self.acessos_titular == -1 else str(self.acessos_titular)

    @property
    def acessos_convidados_display(self):
        return "Ilimitado" if self.acessos_convidados == -1 else str(self.acessos_convidados)

    def __str__(self):
        return f"{self.nome} ({self.cartao})"

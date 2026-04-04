from django.db import models


class InteresseViagemCliente(models.Model):
    CLASSE_CHOICES = [
        ("", "Qualquer classe"),
        ("economica", "Econômica"),
        ("executiva", "Executiva"),
    ]

    cliente = models.ForeignKey(
        "gestao.Cliente",
        on_delete=models.CASCADE,
        related_name="interesses_viagem",
    )
    nome = models.CharField(max_length=120, blank=True)
    continente = models.CharField(max_length=60, blank=True)
    pais = models.CharField(max_length=120, blank=True)
    cidade_destino = models.CharField(max_length=120, blank=True)
    origem = models.CharField(max_length=10, blank=True)
    destino = models.CharField(max_length=10, blank=True)
    classe = models.CharField(max_length=20, choices=CLASSE_CHOICES, blank=True)
    programa_fidelidade = models.CharField(max_length=120, blank=True)
    companhia_aerea = models.CharField(max_length=120, blank=True)
    meses_ida = models.JSONField(default=list, blank=True)
    meses_volta = models.JSONField(default=list, blank=True)
    dias_ida = models.JSONField(default=list, blank=True)
    dias_volta = models.JSONField(default=list, blank=True)
    semestres_ida = models.JSONField(default=list, blank=True)
    semestres_volta = models.JSONField(default=list, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        base = self.nome or self.cidade_destino or self.destino or "Interesse de viagem"
        return f"{self.cliente} - {base}"


class InteresseViagemMatch(models.Model):
    interesse = models.ForeignKey(
        InteresseViagemCliente,
        on_delete=models.CASCADE,
        related_name="matches_alerta",
    )
    alerta = models.ForeignKey(
        "gestao.AlertaViagem",
        on_delete=models.CASCADE,
        related_name="matches_interesse",
    )
    motivos = models.JSONField(default=list, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["interesse", "alerta"],
                name="unique_interesse_alerta_match",
            )
        ]

    def __str__(self):
        return f"{self.interesse} -> {self.alerta}"

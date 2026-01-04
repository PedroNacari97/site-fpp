from django.db import models


class AlertaViagem(models.Model):
    CONTINENTE_CHOICES = [
        ("Europa", "Europa"),
        ("América do Sul", "América do Sul"),
        ("América do Norte", "América do Norte"),
        ("Ásia", "Ásia"),
        ("África", "África"),
        ("Oceania", "Oceania"),
    ]
    CLASSE_ECONOMICA = "economica"
    CLASSE_EXECUTIVA = "executiva"
    CLASSE_CHOICES = [
        (CLASSE_ECONOMICA, "Econômica"),
        (CLASSE_EXECUTIVA, "Executiva"),
    ]

    titulo = models.CharField(max_length=255)
    conteudo = models.TextField(blank=True)
    continente = models.CharField(max_length=60, choices=CONTINENTE_CHOICES)
    pais = models.CharField(max_length=120)
    cidade_destino = models.CharField(max_length=120)
    origem = models.CharField(max_length=10)
    destino = models.CharField(max_length=10)
    classe = models.CharField(max_length=20, choices=CLASSE_CHOICES)
    programa_fidelidade = models.CharField(max_length=120)
    companhia_aerea = models.CharField(max_length=120)
    valor_milhas = models.IntegerField(blank=True, null=True)
    valor_reais = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    datas_ida = models.JSONField(default=list, blank=True)
    datas_volta = models.JSONField(default=list, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.titulo} ({self.origem} → {self.destino})"

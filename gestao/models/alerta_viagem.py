from datetime import date

from django.db import models
from django.utils import timezone


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
    manter_apos_cinco_dias = models.BooleanField(default=False)
    ocultar_apos_datas = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.titulo} ({self.origem} → {self.destino})"

    def datas_disponiveis_validas(self):
        datas_validas = []
        for raw_date in [*(self.datas_ida or []), *(self.datas_volta or [])]:
            if not isinstance(raw_date, str):
                continue
            try:
                datas_validas.append(date.fromisoformat(raw_date))
            except ValueError:
                continue
        return sorted(set(datas_validas))

    def ultima_data_disponivel(self):
        datas = self.datas_disponiveis_validas()
        return datas[-1] if datas else None

    def deve_aparecer_na_vitrine(self, reference_date=None, max_age_days=5):
        if not self.ativo:
            return False

        today = reference_date or timezone.localdate()

        if self.ocultar_apos_datas:
            ultima_data = self.ultima_data_disponivel()
            if ultima_data:
                return ultima_data >= today

        if self.manter_apos_cinco_dias:
            return True

        created_date = (
            timezone.localtime(self.criado_em).date()
            if timezone.is_aware(self.criado_em)
            else self.criado_em.date()
        )
        return (today - created_date).days <= max_age_days

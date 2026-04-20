import uuid

from django.db import models
from django.utils import timezone


class HistoricoVerificacao(models.Model):
    """Registro imutável de cada tentativa de consulta de status de passagem."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    acompanhamento = models.ForeignKey(
        "gestao.AcompanhamentoPassagem",
        on_delete=models.CASCADE,
        related_name="historico",
    )
    verificado_em = models.DateTimeField(default=timezone.now, db_index=True)
    sucesso = models.BooleanField(default=False)
    duracao_ms = models.PositiveIntegerField(default=0)

    status_reserva_anterior = models.CharField(max_length=24, blank=True)
    status_voo_anterior = models.CharField(max_length=24, blank=True)
    status_reserva_novo = models.CharField(max_length=24, blank=True)
    status_voo_novo = models.CharField(max_length=24, blank=True)

    mudou_desde_anterior = models.BooleanField(default=False)
    notificacao_disparada = models.BooleanField(default=False)

    payload_sanitizado = models.JSONField(default=dict, blank=True)
    erro_mensagem = models.TextField(blank=True)
    scraper_nome = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-verificado_em"]
        indexes = [
            models.Index(fields=["acompanhamento", "-verificado_em"], name="hv_acomp_data_idx"),
            models.Index(fields=["mudou_desde_anterior", "-verificado_em"], name="hv_mudou_data_idx"),
        ]

    def __str__(self):
        marcador = "OK" if self.sucesso else "ERRO"
        return f"Verificacao {marcador} em {self.verificado_em:%d/%m/%Y %H:%M}"

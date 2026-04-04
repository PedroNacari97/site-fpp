from django.db import models
from django.utils import timezone


class AcompanhamentoPassagem(models.Model):
    MODO_MANUAL = "manual"
    MODO_SISTEMA_ORIGEM = "sistema_origem"
    MODO_PORTAL_COMPANHIA = "portal_companhia"
    MODO_API_VOO = "api_voo"
    MODO_CONSULTA_CHOICES = (
        (MODO_MANUAL, "Atualizacao manual"),
        (MODO_SISTEMA_ORIGEM, "Sistema de origem"),
        (MODO_PORTAL_COMPANHIA, "Portal da companhia"),
        (MODO_API_VOO, "API de voo"),
    )

    STATUS_RESERVA_NAO_INICIADO = "nao_iniciado"
    STATUS_RESERVA_AGUARDANDO = "aguardando_consulta"
    STATUS_RESERVA_RESERVADO = "reservado"
    STATUS_RESERVA_EMITIDO = "emitido"
    STATUS_RESERVA_TICKETADO = "ticketado"
    STATUS_RESERVA_ALTERADO = "alterado"
    STATUS_RESERVA_CANCELADO = "cancelado"
    STATUS_RESERVA_EMBARCADO = "embarcado"
    STATUS_RESERVA_CONCLUIDO = "concluido"
    STATUS_RESERVA_INCONSISTENTE = "inconsistente"
    STATUS_RESERVA_CHOICES = (
        (STATUS_RESERVA_NAO_INICIADO, "Nao iniciado"),
        (STATUS_RESERVA_AGUARDANDO, "Aguardando consulta"),
        (STATUS_RESERVA_RESERVADO, "Reservado"),
        (STATUS_RESERVA_EMITIDO, "Emitido"),
        (STATUS_RESERVA_TICKETADO, "Ticketado"),
        (STATUS_RESERVA_ALTERADO, "Alterado"),
        (STATUS_RESERVA_CANCELADO, "Cancelado"),
        (STATUS_RESERVA_EMBARCADO, "Embarcado"),
        (STATUS_RESERVA_CONCLUIDO, "Concluido"),
        (STATUS_RESERVA_INCONSISTENTE, "Inconsistente"),
    )

    STATUS_VOO_NAO_CONSULTADO = "nao_consultado"
    STATUS_VOO_PROGRAMADO = "programado"
    STATUS_VOO_CHECKIN = "checkin_aberto"
    STATUS_VOO_EMBARQUE = "embarque_aberto"
    STATUS_VOO_ATRASADO = "atrasado"
    STATUS_VOO_CANCELADO = "cancelado"
    STATUS_VOO_EMBARCADO = "embarcado"
    STATUS_VOO_CONCLUIDO = "concluido"
    STATUS_VOO_CHOICES = (
        (STATUS_VOO_NAO_CONSULTADO, "Nao consultado"),
        (STATUS_VOO_PROGRAMADO, "Programado"),
        (STATUS_VOO_CHECKIN, "Check-in aberto"),
        (STATUS_VOO_EMBARQUE, "Embarque aberto"),
        (STATUS_VOO_ATRASADO, "Atrasado"),
        (STATUS_VOO_CANCELADO, "Cancelado"),
        (STATUS_VOO_EMBARCADO, "Embarcado"),
        (STATUS_VOO_CONCLUIDO, "Concluido"),
    )

    emissao = models.OneToOneField(
        "gestao.EmissaoPassagem",
        on_delete=models.CASCADE,
        related_name="acompanhamento",
    )
    modo_consulta = models.CharField(
        max_length=24,
        choices=MODO_CONSULTA_CHOICES,
        default=MODO_MANUAL,
    )
    sistema_origem = models.CharField(max_length=120, blank=True)
    referencia_externa = models.CharField(max_length=120, blank=True)
    localizador_consulta = models.CharField(max_length=100, blank=True)
    sobrenome_consulta = models.CharField(max_length=120, blank=True)
    email_consulta = models.EmailField(blank=True)
    status_reserva = models.CharField(
        max_length=24,
        choices=STATUS_RESERVA_CHOICES,
        default=STATUS_RESERVA_NAO_INICIADO,
    )
    status_voo = models.CharField(
        max_length=24,
        choices=STATUS_VOO_CHOICES,
        default=STATUS_VOO_NAO_CONSULTADO,
    )
    ultimo_resumo = models.TextField(blank=True)
    orientacao_operacional = models.TextField(blank=True)
    payload_bruto_json = models.JSONField(default=dict, blank=True)
    ultima_sincronizacao_em = models.DateTimeField(null=True, blank=True)
    proxima_verificacao_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Acompanhamento de passagem"
        verbose_name_plural = "Acompanhamentos de passagens"
        ordering = ["-atualizado_em"]

    def __str__(self):
        return f"Acompanhamento da emissao #{self.emissao_id}"

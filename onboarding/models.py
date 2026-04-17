from django.conf import settings
from django.db import models
from django.utils import timezone


class Plano(models.Model):
    nome = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    descricao = models.TextField(blank=True)
    preco_mensal = models.DecimalField(max_digits=10, decimal_places=2)
    preco_anual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    limite_operadores = models.PositiveIntegerField(default=3)
    limite_clientes = models.PositiveIntegerField(default=0, help_text="0 = ilimitado")
    features = models.JSONField(default=dict, blank=True)
    trial_dias = models.PositiveIntegerField(default=14)
    ativo = models.BooleanField(default=True)
    destaque = models.BooleanField(default=False, help_text="Plano recomendado (destaque visual)")
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "preco_mensal"]
        verbose_name = "Plano"
        verbose_name_plural = "Planos"

    def __str__(self):
        return self.nome


class Assinatura(models.Model):
    STATUS_TRIAL = "trial"
    STATUS_ATIVA = "ativa"
    STATUS_INADIMPLENTE = "inadimplente"
    STATUS_SUSPENSA = "suspensa"
    STATUS_CANCELADA = "cancelada"

    STATUS_CHOICES = [
        (STATUS_TRIAL, "Trial"),
        (STATUS_ATIVA, "Ativa"),
        (STATUS_INADIMPLENTE, "Inadimplente"),
        (STATUS_SUSPENSA, "Suspensa"),
        (STATUS_CANCELADA, "Cancelada"),
    ]

    empresa = models.OneToOneField(
        "gestao.Empresa", on_delete=models.CASCADE, related_name="assinatura"
    )
    plano = models.ForeignKey(Plano, on_delete=models.PROTECT, related_name="assinaturas")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL, db_index=True)
    gateway_customer_id = models.CharField(max_length=120, blank=True)
    gateway_subscription_id = models.CharField(max_length=120, blank=True, db_index=True)
    data_inicio = models.DateTimeField(default=timezone.now)
    trial_fim = models.DateTimeField(null=True, blank=True)
    data_vencimento = models.DateTimeField(null=True, blank=True)
    cancelada_em = models.DateTimeField(null=True, blank=True)
    ref_vendedor = models.CharField(max_length=60, blank=True, help_text="Codigo do vendedor que indicou")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Assinatura"
        verbose_name_plural = "Assinaturas"

    def __str__(self):
        return f"{self.empresa} \u2014 {self.plano} ({self.get_status_display()})"

    @property
    def is_ativa(self):
        if self.status == self.STATUS_ATIVA:
            return True
        if self.status == self.STATUS_TRIAL and self.trial_fim and self.trial_fim > timezone.now():
            return True
        return False

    @property
    def trial_expirado(self):
        if self.status != self.STATUS_TRIAL:
            return False
        return self.trial_fim and self.trial_fim <= timezone.now()

    @property
    def dias_restantes_trial(self):
        if not self.trial_fim:
            return 0
        delta = self.trial_fim - timezone.now()
        return max(0, delta.days)


class Pagamento(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_CONFIRMADO = "confirmado"
    STATUS_FALHOU = "falhou"
    STATUS_ESTORNADO = "estornado"

    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_CONFIRMADO, "Confirmado"),
        (STATUS_FALHOU, "Falhou"),
        (STATUS_ESTORNADO, "Estornado"),
    ]

    METODO_CARTAO = "cartao"
    METODO_PIX = "pix"
    METODO_BOLETO = "boleto"

    METODO_CHOICES = [
        (METODO_CARTAO, "Cartao de credito"),
        (METODO_PIX, "PIX"),
        (METODO_BOLETO, "Boleto"),
    ]

    assinatura = models.ForeignKey(Assinatura, on_delete=models.CASCADE, related_name="pagamentos")
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE, db_index=True)
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES, blank=True)
    gateway_ref = models.CharField(max_length=120, unique=True, db_index=True)
    gateway_event_type = models.CharField(max_length=80, blank=True)
    dados_gateway = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"R$ {self.valor} \u2014 {self.get_status_display()} ({self.gateway_ref})"

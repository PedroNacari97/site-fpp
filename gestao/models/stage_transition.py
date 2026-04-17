from django.conf import settings
from django.db import models


STAGES = (
    ("novo_pedido", "Novo pedido", None),
    ("cotacao_enviada", "Cotacao enviada", None),
    ("aprovada", "Aprovada", None),
    ("em_emissao", "Em emissao", None),
    ("emitida", "Emitida", None),
    ("finalizada", "Finalizada", None),
    ("cancelada", "Cancelada", None),
)

TRANSICOES = {
    "novo_pedido": {"cotacao_enviada", "cancelada"},
    "cotacao_enviada": {"aprovada", "cancelada", "novo_pedido"},
    "aprovada": {"em_emissao", "cancelada", "cotacao_enviada"},
    "em_emissao": {"emitida", "cancelada", "aprovada"},
    "emitida": {"finalizada", "cancelada"},
    "finalizada": set(),
    "cancelada": {"novo_pedido"},
}


class StageTransition(models.Model):
    """Auditoria de transicoes do Pipeline (Cotacao+Emissao).

    Guarda origem, destino, usuario e timestamp de cada movimento
    no kanban. Aponta opcionalmente para CotacaoVoo ou EmissaoPassagem.
    """

    STAGE_CHOICES = tuple(
        (slug, label) for slug, label, _ in STAGES
    ) + (
        ("lead", "Lead (legacy)"),
        ("aceita", "Aceita (legacy)"),
        ("concluida", "Concluida (legacy)"),
    )

    MOVED_VIA_CHOICES = (
        ("drag", "Drag and drop"),
        ("button", "Botao / bottom-sheet"),
        ("system", "Sistema"),
    )

    cotacao = models.ForeignKey(
        "gestao.CotacaoVoo", on_delete=models.CASCADE, null=True, blank=True, related_name="transicoes_stage"
    )
    emissao = models.ForeignKey(
        "gestao.EmissaoPassagem", on_delete=models.CASCADE, null=True, blank=True, related_name="transicoes_stage"
    )
    stage_origem = models.CharField(max_length=20, choices=STAGE_CHOICES)
    stage_destino = models.CharField(max_length=20, choices=STAGE_CHOICES)
    moved_via = models.CharField(max_length=16, choices=MOVED_VIA_CHOICES, default="button", blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["stage_destino", "criado_em"]),
        ]
        ordering = ["-criado_em"]

    def __str__(self):
        alvo = self.cotacao_id or self.emissao_id
        return f"{self.stage_origem} -> {self.stage_destino} (#{alvo})"

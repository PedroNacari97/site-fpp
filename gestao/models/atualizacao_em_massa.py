from django.conf import settings
from django.db import models
from django.utils import timezone


class AtualizacaoEmMassa(models.Model):
    STATUS_EM_ANDAMENTO = "em_andamento"
    STATUS_CONCLUIDO = "concluido"
    STATUS_INTERROMPIDO = "interrompido"
    STATUS_ERRO = "erro"
    STATUS_CHOICES = (
        (STATUS_EM_ANDAMENTO, "Em andamento"),
        (STATUS_CONCLUIDO, "Concluído"),
        (STATUS_INTERROMPIDO, "Interrompido"),
        (STATUS_ERRO, "Erro"),
    )

    empresa = models.ForeignKey(
        "gestao.Empresa",
        on_delete=models.CASCADE,
        related_name="atualizacoes_em_massa",
        db_index=True,
    )
    iniciado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atualizacoes_em_massa_iniciadas",
    )
    iniciado_em = models.DateTimeField(default=timezone.now, db_index=True)
    concluido_em = models.DateTimeField(null=True, blank=True)
    total = models.PositiveIntegerField(default=0)
    ok = models.PositiveIntegerField(default=0)
    sem_mudanca = models.PositiveIntegerField(default=0)
    com_mudanca = models.PositiveIntegerField(default=0)
    erro = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_EM_ANDAMENTO,
        db_index=True,
    )
    resultado = models.JSONField(default=list, blank=True)
    mensagem_erro = models.TextField(blank=True)

    class Meta:
        verbose_name = "Atualização em massa"
        verbose_name_plural = "Atualizações em massa"
        ordering = ["-iniciado_em"]
        indexes = [
            models.Index(fields=["empresa", "-iniciado_em"]),
            models.Index(fields=["status", "iniciado_em"]),
        ]

    def __str__(self):
        return f"Atualização #{self.pk} ({self.empresa_id}) {self.status}"

    @property
    def progresso_pct(self):
        if not self.total:
            return 0
        processados = self.ok + self.erro
        return min(100, int(round(processados * 100 / self.total)))

    @property
    def em_andamento(self):
        return self.status == self.STATUS_EM_ANDAMENTO

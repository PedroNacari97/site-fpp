from datetime import timedelta

from django.db import models
from django.utils import timezone

from gestao.utils import normalize_cpf

from .conta_fidelidade import ContaFidelidade


class UsoCPF(models.Model):
    conta_fidelidade = models.ForeignKey(
        ContaFidelidade,
        on_delete=models.CASCADE,
        related_name="usos_cpf",
    )
    cpf = models.CharField(max_length=11)
    cpf_hash = models.CharField(max_length=64, blank=True, db_index=True)
    data_ultima_emissao = models.DateField()

    class Meta:
        verbose_name = "Uso de CPF"
        verbose_name_plural = "Usos de CPF"
        ordering = ["cpf"]
        unique_together = ("conta_fidelidade", "cpf")

    def save(self, *args, **kwargs):
        self.cpf = normalize_cpf(self.cpf)
        super().save(*args, **kwargs)

    @property
    def proxima_liberacao(self):
        programa = self.conta_fidelidade.programa
        if programa.tipo_regra_reset == programa.REGRA_RESET_DIAS and programa.dias_reset:
            return self.data_ultima_emissao + timedelta(days=programa.dias_reset)
        return self.data_ultima_emissao.replace(month=1, day=1, year=self.data_ultima_emissao.year + 1)

    @property
    def liberado(self):
        hoje = timezone.localdate()
        programa = self.conta_fidelidade.programa
        if programa.tipo_regra_reset == programa.REGRA_RESET_DIAS and programa.dias_reset:
            return hoje >= self.data_ultima_emissao + timedelta(days=programa.dias_reset)
        return hoje.year > self.data_ultima_emissao.year

    def __str__(self):
        return f"{self.conta_fidelidade} - {self.cpf}"

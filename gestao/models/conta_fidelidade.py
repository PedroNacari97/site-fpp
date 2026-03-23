from django.core.exceptions import ValidationError
from django.db import models

from gestao.utils import normalize_cpf

from .cliente import Cliente
from .conta_administrada import ContaAdministrada
from .programa_fidelidade import ProgramaFidelidade


class ContaFidelidade(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True)
    conta_administrada = models.ForeignKey(
        ContaAdministrada,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="contas_fidelidade",
    )
    programa = models.ForeignKey(ProgramaFidelidade, on_delete=models.CASCADE)

    login_programa = models.CharField(
        max_length=150, blank=True, help_text="Login do titular junto ao programa"
    )
    senha_programa = models.CharField(
        max_length=150, blank=True, help_text="Senha do titular junto ao programa"
    )
    titular_programa_info = models.TextField(
        blank=True,
        help_text="Informações adicionais do titular (ex.: nome completo, CPF, dados de resgate)",
    )
    observacoes_programa = models.TextField(
        blank=True,
        help_text="Observações gerais sobre o uso do programa para esta conta",
    )
    quantidade_cpfs_disponiveis = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Quantidade de CPFs que ainda podem ser utilizados com este programa. Deixe vazio para ilimitado.",
    )

    PERIODICIDADE_CLUBE = (
        ("nenhum", "Nenhum"),
        ("mensal", "Mensal"),
        ("trimestral", "Trimestral"),
        ("semestral", "Semestral"),
        ("anual", "Anual"),
    )
    clube_periodicidade = models.CharField(
        max_length=12, choices=PERIODICIDADE_CLUBE, default="nenhum"
    )
    pontos_clube_mes = models.IntegerField(default=0)
    valor_assinatura_clube = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    data_inicio_clube = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)

    def clean(self):
        super().clean()
        if bool(self.cliente) == bool(self.conta_administrada):
            raise ValidationError("Informe um cliente ou uma conta administrada, mas não ambos.")

    @property
    def empresa(self):
        if self.cliente_id:
            return self.cliente.empresa
        if self.conta_administrada_id:
            return self.conta_administrada.empresa
        return None

    @property
    def programa_base(self):
        return self.programa.programa_base if self.programa.is_vinculado else None

    def conta_saldo(self):
        if not self.programa.is_vinculado:
            return self
        filtros = {"programa": self.programa.programa_base}
        if self.cliente_id:
            filtros["cliente"] = self.cliente
        if self.conta_administrada_id:
            filtros["conta_administrada"] = self.conta_administrada
        return ContaFidelidade.objects.filter(**filtros).select_related("programa").first() or self

    @property
    def valor_medio_por_mil(self):
        saldo = self.saldo_pontos
        if self.programa.is_vinculado and saldo > 0 and getattr(self.programa, "preco_medio_milheiro", None):
            return float(self.programa.preco_medio_milheiro)
        if saldo > 0:
            return float(self.valor_total_pago) / (saldo / 1000)
        return 0

    @property
    def saldo_pontos(self):
        conta_base = self.conta_saldo()
        movs = conta_base.movimentacoes.all()
        return sum(m.pontos for m in movs) if movs.exists() else 0

    @property
    def valor_total_pago(self):
        conta_base = self.conta_saldo()
        movs = conta_base.movimentacoes.all()
        return sum(float(m.valor_pago) for m in movs) if movs.exists() else 0

    @property
    def limite_cpfs(self):
        return self.programa.limite_cpfs

    def get_usos_cpf_queryset(self):
        return self.usos_cpf.select_related("conta_fidelidade__programa")

    @property
    def cpfs_usados(self):
        return self.get_usos_cpf_queryset().filter(data_ultima_emissao__isnull=False).count()

    @property
    def cpfs_utilizados(self):
        return self.cpfs_usados

    @property
    def cpfs_disponiveis(self):
        limite = self.limite_cpfs
        if limite is None:
            return None
        return max(limite - self.cpfs_usados, 0)

    @property
    def status_cpf(self):
        limite = self.limite_cpfs
        if limite is None:
            return {"tone": "disponivel", "label": "Disponível", "ratio": 0}
        usados = self.cpfs_usados
        if usados >= limite:
            return {"tone": "bloqueado", "label": "Bloqueado", "ratio": 1}
        ratio = usados / limite if limite else 0
        if ratio >= 0.8:
            return {"tone": "proximo", "label": "Próximo do limite", "ratio": ratio}
        return {"tone": "disponivel", "label": "Disponível", "ratio": ratio}

    @property
    def movimentacoes_compartilhadas(self):
        return self.conta_saldo().movimentacoes.all()

    def cpf_ja_utilizado(self, cpf):
        cpf = normalize_cpf(cpf)
        return self.usos_cpf.filter(cpf=cpf).exists()

    def __str__(self):
        titular = self.cliente or self.conta_administrada
        return f"{titular} - {self.programa}"

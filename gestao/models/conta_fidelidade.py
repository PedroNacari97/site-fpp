from django.core.exceptions import ValidationError
from django.db import models
from .cliente import Cliente
from .programa_fidelidade import ProgramaFidelidade
from .conta_administrada import ContaAdministrada
from gestao.utils import normalize_cpf


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
        """Conta que efetivamente guarda saldo/movimentações (programa base)."""
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
        """
        Calcula o valor médio por mil pontos para este programa.
        
        IMPORTANTE: O valor médio é SEMPRE calculado dividindo o valor pago
        pela quantidade de pontos, independente se é programa base ou vinculado.
        
        Fórmula: valor_pago / (saldo_pontos / 1000)
        
        Exemplo:
        - Azul Pelo Mundo: R$ 610 / (44.000 / 1000) = R$ 13.86 por mil
        - Livelo: R$ 915 / (30.000 / 1000) = R$ 30.50 por mil
        - Smiles: R$ 915 / (60.000 / 1000) = R$ 15.25 por mil
        
        O preco_medio_milheiro do programa é para o VALOR DE REFERÊNCIA,
        não para o custo médio calculado.
        """
        
        # Sempre calcular com saldo/valor da conta base
        saldo = self.saldo_pontos
        if saldo > 0:
            return float(self.valor_total_pago) / (saldo / 1000)
        return 0

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
    def cpfs_utilizados(self):
        limite = self.quantidade_cpfs_disponiveis
        if limite is None:
            return None
        from gestao.models import Passageiro

        filtros = {"emissao__programa_id": self.programa_id}
        if self.cliente_id:
            filtros["emissao__cliente_id"] = self.cliente_id
            filtros["emissao__conta_administrada__isnull"] = True
        if self.conta_administrada_id:
            filtros["emissao__conta_administrada_id"] = self.conta_administrada_id
        cpfs = set()
        for cpf in Passageiro.objects.filter(**filtros).values_list("cpf", flat=True):
            normalized = normalize_cpf(cpf)
            if normalized:
                cpfs.add(normalized)
        return len(cpfs)

    @property
    def cpfs_disponiveis(self):
        limite = self.quantidade_cpfs_disponiveis
        if limite is None:
            return None
        usados = self.cpfs_utilizados or 0
        return max(limite - usados, 0)

    @property
    def movimentacoes_compartilhadas(self):
        return self.conta_saldo().movimentacoes.all()

    def __str__(self):
        titular = self.cliente or self.conta_administrada
        return f"{titular} - {self.programa}"

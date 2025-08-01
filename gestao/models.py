from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal



class Cliente(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="cliente_gestao"
    )
    telefone = models.CharField(max_length=20, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    cpf = models.CharField(max_length=14, default="000.000.000-00")
    PERFIS = (
        ("admin", "Administrador"),
        ("operador", "Operador"),
        ("cliente", "Cliente"),
    )
    perfil = models.CharField(max_length=10, choices=PERFIS, default="cliente")
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username


class ProgramaFidelidade(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    preco_medio_milheiro = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    def __str__(self):
        return self.nome


class Aeroporto(models.Model):
    nome = models.CharField(max_length=200)
    sigla = models.CharField(max_length=10)
    cidade = models.CharField(max_length=200)
    estado = models.CharField(max_length=100)

    class Meta:
        ordering = ["sigla"]

    def __str__(self):
        return f"{self.sigla} - {self.nome}"


class ContaFidelidade(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    programa = models.ForeignKey(ProgramaFidelidade, on_delete=models.CASCADE)

    @property
    def valor_medio_por_mil(self):
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
        movs = self.movimentacoes.all()
        return sum(m.pontos for m in movs) if movs.exists() else 0

    @property
    def valor_total_pago(self):
        movs = self.movimentacoes.all()
        return sum(float(m.valor_pago) for m in movs) if movs.exists() else 0

    def __str__(self):
        return f"{self.cliente} - {self.programa}"

    def __str__(self):
        return f"{self.conta} - {self.data:%d/%m/%Y} - {self.pontos}"


class EmissaoPassagem(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    programa = models.ForeignKey(
        ProgramaFidelidade, on_delete=models.CASCADE, null=True, blank=True
    )
    aeroporto_partida = models.ForeignKey(
        Aeroporto,
        on_delete=models.CASCADE,
        related_name="partidas",
        null=True,
        blank=True,
    )
    aeroporto_destino = models.ForeignKey(
        Aeroporto,
        on_delete=models.CASCADE,
        related_name="destinos",
        null=True,
        blank=True,
    )
    data_ida = models.DateTimeField()
    data_volta = models.DateTimeField(null=True, blank=True)
    qtd_passageiros = models.PositiveIntegerField()
    companhia_aerea = models.CharField(max_length=100, blank=True)
    localizador = models.CharField(max_length=100, blank=True)
    valor_referencia = models.DecimalField(max_digits=10, decimal_places=2)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    pontos_utilizados = models.IntegerField(null=True, blank=True)
    valor_referencia_pontos = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    economia_obtida = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    detalhes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.cliente} - {self.programa} - {self.data_ida}"


class ValorMilheiro(models.Model):
    programa_nome = models.CharField(max_length=50, unique=True)
    valor_mercado = models.DecimalField(
        max_digits=8, decimal_places=2
    )  # Exemplo: 37.50
    atualizado_em = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.programa_nome} (R$ {self.valor_mercado})"


class Movimentacao(models.Model):
    conta = models.ForeignKey(
        ContaFidelidade, on_delete=models.CASCADE, related_name="movimentacoes"
    )
    data = models.DateField()
    pontos = models.IntegerField()
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    descricao = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.conta} - {self.data} - {self.pontos}"


class EmissaoHotel(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    nome_hotel = models.CharField(max_length=200)
    check_in = models.DateField()
    check_out = models.DateField()
    valor_referencia = models.DecimalField(max_digits=10, decimal_places=2)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    economia_obtida = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return f"{self.cliente} - {self.nome_hotel}"


class AcessoClienteLog(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    data_acesso = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.admin} -> {self.cliente} em {self.data_acesso:%d/%m/%Y %H:%M}"


class CotacaoVoo(models.Model):
    STATUS_CHOICES = (
        ("pendente", "Pendente"),
        ("aceita", "Aceita"),
        ("rejeitada", "Rejeitada"),
        ("emissao", "Emissão"),
    )

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    companhia_aerea = models.CharField(max_length=100, blank=True)
    origem = models.ForeignKey(
        Aeroporto,
        related_name="cotacoes_origem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    destino = models.ForeignKey(
        Aeroporto,
        related_name="cotacoes_destino",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    data_ida = models.DateTimeField()
    data_volta = models.DateTimeField(null=True, blank=True)
    programa = models.ForeignKey(
        ProgramaFidelidade, on_delete=models.SET_NULL, null=True, blank=True
    )
    qtd_passageiros = models.PositiveIntegerField(default=1)
    classe = models.CharField(max_length=50, blank=True)
    observacoes = models.TextField(blank=True)
    valor_passagem = models.DecimalField(max_digits=10, decimal_places=2)
    taxas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    milhas = models.IntegerField(default=0)
    valor_milheiro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    parcelas = models.IntegerField(default=1)
    juros = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)      # 1.00 = sem juros
    desconto = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)   # 1.00 = sem desconto
    valor_parcelado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_vista = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    validade = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    economia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    emissao = models.OneToOneField(
        "EmissaoPassagem", on_delete=models.SET_NULL, null=True, blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    def calcular_valores(self):
        base = (Decimal(self.milhas) / Decimal('1000')) * Decimal(self.valor_milheiro) + Decimal(self.taxas)
        parcelado = base * Decimal(self.juros)         # juros deve ser algo tipo 1.13
        avista = parcelado * Decimal(self.desconto)    # desconto deve ser algo tipo 0.95
        self.valor_parcelado = parcelado
        self.valor_vista = avista
        self.economia = Decimal(self.valor_passagem) - avista

    def save(self, *args, **kwargs):
        self.calcular_valores()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente} - {self.origem} -> {self.destino} ({self.data_ida})"

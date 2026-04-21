"""
Models administrativos do NCfly — usados exclusivamente pelo /ncadm/.

- CustoOperacional: despesas operacionais (Railway, OpenAI, dominio, etc.),
  com cambio PTAX e IOF quando em USD. Input manual mensal por Pedro.
- ObrigacaoFiscal: lembretes de obrigacoes acessorias (DAS, DEFIS, NFS-e).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import models
from django.utils import timezone


class CustoOperacional(models.Model):
    """Despesa operacional recorrente ou avulsa.

    Campos USD sao preenchidos quando o pagamento foi em moeda estrangeira
    (cartao internacional). cambio_ptax e valor_brl sao obrigatorios para
    fechamento contabil e para calculo de margem no dashboard.
    """

    CATEGORIA_INFRA = "infra"
    CATEGORIA_IA = "ia"
    CATEGORIA_DOMINIO = "dominio"
    CATEGORIA_MARKETING = "marketing"
    CATEGORIA_FERRAMENTAS = "ferramentas"
    CATEGORIA_PESSOAL = "pessoal"
    CATEGORIA_OUTROS = "outros"

    CATEGORIA_CHOICES = (
        (CATEGORIA_INFRA, "Infraestrutura (Railway, Cloudflare)"),
        (CATEGORIA_IA, "IA (OpenAI, Anthropic)"),
        (CATEGORIA_DOMINIO, "Dominio / SSL"),
        (CATEGORIA_MARKETING, "Marketing / Ads"),
        (CATEGORIA_FERRAMENTAS, "Ferramentas SaaS"),
        (CATEGORIA_PESSOAL, "Pessoal / Servicos"),
        (CATEGORIA_OUTROS, "Outros"),
    )

    MOEDA_BRL = "BRL"
    MOEDA_USD = "USD"
    MOEDA_CHOICES = (
        (MOEDA_BRL, "Real (BRL)"),
        (MOEDA_USD, "Dolar (USD)"),
    )

    mes_referencia = models.DateField(
        db_index=True,
        help_text="Primeiro dia do mes a que o custo se refere (YYYY-MM-01).",
    )
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default=CATEGORIA_OUTROS,
        db_index=True,
    )
    fornecedor = models.CharField(max_length=120)
    descricao = models.CharField(max_length=240, blank=True, default="")

    moeda = models.CharField(max_length=3, choices=MOEDA_CHOICES, default=MOEDA_BRL)
    valor_original = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Valor na moeda original.",
    )
    cambio_ptax = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("1.0000"),
        help_text="Cambio PTAX do dia do pagamento. 1.0000 quando BRL.",
    )
    iof = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="IOF pago (3,5% em cartao internacional, zero em BRL).",
    )
    valor_brl = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Valor total em BRL (valor_original * cambio + iof).",
    )

    tem_invoice = models.BooleanField(
        default=False,
        help_text="Se o fornecedor emitiu invoice/receipt valido.",
    )
    anexo = models.FileField(
        upload_to="ncadm/custos/%Y/%m/",
        blank=True, null=True,
        help_text="PDF da invoice/recibo (opcional).",
    )
    observacoes = models.TextField(blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Custo operacional"
        verbose_name_plural = "Custos operacionais"
        ordering = ["-mes_referencia", "categoria", "fornecedor"]
        indexes = [
            models.Index(fields=["mes_referencia", "categoria"]),
        ]

    def __str__(self) -> str:
        return f"{self.mes_referencia:%Y-%m} {self.fornecedor} R$ {self.valor_brl}"

    @classmethod
    def normalizar_mes(cls, ref: date | None = None) -> date:
        if ref is None:
            ref = timezone.now().date()
        return ref.replace(day=1)


class ObrigacaoFiscal(models.Model):
    """Obrigacao acessoria com prazo (DAS, DEFIS, NFS-e, etc.).

    Pedro marca como paga/entregue. Dashboard exibe as vencendo nos proximos 30 dias.
    """

    TIPO_DAS = "das"
    TIPO_DEFIS = "defis"
    TIPO_NFSE = "nfse"
    TIPO_DCTFWEB = "dctfweb"
    TIPO_ESOCIAL = "esocial"
    TIPO_DASN_SIMEI = "dasn_simei"
    TIPO_OUTRA = "outra"

    TIPO_CHOICES = (
        (TIPO_DAS, "DAS (Simples Nacional)"),
        (TIPO_DEFIS, "DEFIS anual"),
        (TIPO_NFSE, "Emissao NFS-e"),
        (TIPO_DCTFWEB, "DCTFWeb / eSocial mensal"),
        (TIPO_ESOCIAL, "eSocial"),
        (TIPO_DASN_SIMEI, "DASN-SIMEI (MEI)"),
        (TIPO_OUTRA, "Outra"),
    )

    STATUS_PENDENTE = "pendente"
    STATUS_PAGA = "paga"
    STATUS_ATRASADA = "atrasada"
    STATUS_CHOICES = (
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_PAGA, "Paga / Entregue"),
        (STATUS_ATRASADA, "Atrasada"),
    )

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_OUTRA)
    descricao = models.CharField(max_length=180)
    competencia = models.DateField(
        help_text="Mes/ano de competencia (YYYY-MM-01).",
    )
    vencimento = models.DateField(db_index=True)
    valor_estimado = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE, db_index=True,
    )
    pago_em = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Obrigacao fiscal"
        verbose_name_plural = "Obrigacoes fiscais"
        ordering = ["vencimento"]
        indexes = [
            models.Index(fields=["status", "vencimento"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.competencia:%Y-%m} — venc {self.vencimento:%d/%m}"

    @property
    def dias_para_vencer(self) -> int:
        return (self.vencimento - timezone.now().date()).days

    @property
    def esta_atrasada(self) -> bool:
        return self.status != self.STATUS_PAGA and self.vencimento < timezone.now().date()


class PerfilFiscal(models.Model):
    """Perfil fiscal da empresa NCfly (singleton). Usado como fonte de verdade
    para regime tributario, CNAEs, contador e status da conversao I.S. -> ME.
    """

    REGIME_INOVA_SIMPLES = "inova_simples"
    REGIME_MEI = "mei"
    REGIME_ME_SIMPLES = "me_simples"
    REGIME_EPP_SIMPLES = "epp_simples"
    REGIME_LP = "lucro_presumido"
    REGIME_LR = "lucro_real"
    REGIME_CHOICES = (
        (REGIME_INOVA_SIMPLES, "Inova Simples (I.S.)"),
        (REGIME_MEI, "MEI"),
        (REGIME_ME_SIMPLES, "ME - Simples Nacional"),
        (REGIME_EPP_SIMPLES, "EPP - Simples Nacional"),
        (REGIME_LP, "Lucro Presumido"),
        (REGIME_LR, "Lucro Real"),
    )

    CONVERSAO_NAO_INICIADA = "nao_iniciada"
    CONVERSAO_EM_ANDAMENTO = "em_andamento"
    CONVERSAO_CONCLUIDA = "concluida"
    CONVERSAO_CHOICES = (
        (CONVERSAO_NAO_INICIADA, "Nao iniciada"),
        (CONVERSAO_EM_ANDAMENTO, "Em andamento"),
        (CONVERSAO_CONCLUIDA, "Concluida"),
    )

    # Identificacao
    razao_social = models.CharField(max_length=180, blank=True, default="")
    nome_fantasia = models.CharField(max_length=120, blank=True, default="")
    cnpj = models.CharField(max_length=18, blank=True, default="", help_text="00.000.000/0000-00")
    data_abertura = models.DateField(null=True, blank=True)
    endereco = models.CharField(max_length=240, blank=True, default="")
    municipio = models.CharField(max_length=80, blank=True, default="")
    uf = models.CharField(max_length=2, blank=True, default="")

    # Regime tributario
    regime_atual = models.CharField(
        max_length=20, choices=REGIME_CHOICES, default=REGIME_INOVA_SIMPLES,
    )
    anexo_simples = models.CharField(
        max_length=5, blank=True, default="",
        help_text="Anexo do Simples Nacional aplicavel (III, IV, V). SaaS geralmente Anexo III.",
    )
    cnae_principal = models.CharField(
        max_length=20, blank=True, default="",
        help_text="Ex.: 6202-3/00 - Desenvolvimento e licenciamento de software customizavel.",
    )
    cnaes_secundarios = models.TextField(
        blank=True, default="",
        help_text="Um CNAE por linha.",
    )

    # Municipal
    inscricao_municipal = models.CharField(max_length=40, blank=True, default="")
    inscricao_estadual = models.CharField(max_length=40, blank=True, default="")
    iss_aliquota = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        help_text="Aliquota de ISS em % (ex.: 2.00, 5.00).",
    )
    nfse_portal_url = models.URLField(blank=True, default="")

    # Contador
    contador_nome = models.CharField(max_length=120, blank=True, default="")
    contador_crc = models.CharField(max_length=30, blank=True, default="")
    contador_email = models.EmailField(blank=True, default="")
    contador_telefone = models.CharField(max_length=30, blank=True, default="")
    contador_escritorio = models.CharField(max_length=120, blank=True, default="")

    # Conversao I.S. -> ME
    regime_alvo = models.CharField(
        max_length=20, choices=REGIME_CHOICES, blank=True, default="",
        help_text="Regime para o qual a empresa esta migrando (se houver).",
    )
    conversao_status = models.CharField(
        max_length=20, choices=CONVERSAO_CHOICES, default=CONVERSAO_NAO_INICIADA,
    )
    conversao_iniciada_em = models.DateField(null=True, blank=True)
    conversao_prevista_para = models.DateField(null=True, blank=True)
    conversao_concluida_em = models.DateField(null=True, blank=True)
    conversao_checklist = models.TextField(
        blank=True, default="",
        help_text="Checklist livre (um item por linha). Prefixar com [x] para concluidos.",
    )

    observacoes = models.TextField(blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil fiscal"
        verbose_name_plural = "Perfil fiscal"

    def __str__(self) -> str:
        return f"{self.razao_social or 'Perfil fiscal'} ({self.get_regime_atual_display()})"

    @classmethod
    def get_singleton(cls) -> "PerfilFiscal":
        obj = cls.objects.order_by("pk").first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    @property
    def cnaes_secundarios_lista(self) -> list[str]:
        return [linha.strip() for linha in self.cnaes_secundarios.splitlines() if linha.strip()]

    @property
    def checklist_itens(self) -> list[dict]:
        itens = []
        for linha in self.conversao_checklist.splitlines():
            stripped = linha.strip()
            if not stripped:
                continue
            feito = stripped.lower().startswith("[x]")
            texto = stripped[3:].strip() if feito else stripped
            if texto.startswith("[ ]"):
                texto = texto[3:].strip()
            itens.append({"feito": feito, "texto": texto})
        return itens


class RecebimentoReceita(models.Model):
    """Recebimento bruto (um por transacao) que compoe a receita tributavel do mes.

    Um registro por pagamento recebido — via adquirente (Stripe, Asaas,
    Mercado Pago), Pix direto, boleto, TED. Base para calcular o DAS do
    Simples Nacional Anexo III.
    """

    ORIGEM_ADQUIRENTE = "adquirente"
    ORIGEM_PIX = "pix"
    ORIGEM_BOLETO = "boleto"
    ORIGEM_TED = "ted"
    ORIGEM_OUTRO = "outro"
    ORIGEM_CHOICES = (
        (ORIGEM_ADQUIRENTE, "Adquirente (Stripe, Asaas, MP)"),
        (ORIGEM_PIX, "Pix direto"),
        (ORIGEM_BOLETO, "Boleto"),
        (ORIGEM_TED, "TED / transferencia"),
        (ORIGEM_OUTRO, "Outro"),
    )

    NATUREZA_SAAS = "saas"
    NATUREZA_SERVICO = "servico"
    NATUREZA_OUTRO = "outro"
    NATUREZA_CHOICES = (
        (NATUREZA_SAAS, "Assinatura SaaS B2B"),
        (NATUREZA_SERVICO, "Servico avulso"),
        (NATUREZA_OUTRO, "Outro"),
    )

    data = models.DateField(db_index=True, help_text="Data em que o valor caiu na conta.")
    mes_competencia = models.DateField(
        db_index=True,
        help_text="Primeiro dia do mes de competencia (YYYY-MM-01). Preenchido automaticamente.",
    )
    cliente = models.CharField(max_length=180, blank=True, default="")
    natureza = models.CharField(
        max_length=20, choices=NATUREZA_CHOICES, default=NATUREZA_SAAS,
    )
    origem = models.CharField(
        max_length=20, choices=ORIGEM_CHOICES, default=ORIGEM_ADQUIRENTE,
    )
    valor_bruto = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Valor bruto recebido (base para o Simples).",
    )
    taxa_adquirente = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Taxa descontada pelo adquirente (informativa, NAO reduz o Simples).",
    )
    descricao = models.CharField(max_length=240, blank=True, default="")
    nfse_emitida = models.BooleanField(
        default=False,
        help_text="Se a NFS-e correspondente ja foi emitida na prefeitura.",
    )
    nfse_numero = models.CharField(max_length=40, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Recebimento de receita"
        verbose_name_plural = "Recebimentos de receita"
        ordering = ["-data", "-criado_em"]
        indexes = [
            models.Index(fields=["mes_competencia", "natureza"]),
        ]

    def __str__(self) -> str:
        return f"{self.data:%d/%m/%Y} {self.cliente or '-'} R$ {self.valor_bruto}"

    def save(self, *args, **kwargs):
        if self.data and not self.mes_competencia:
            self.mes_competencia = self.data.replace(day=1)
        super().save(*args, **kwargs)

    @property
    def valor_liquido(self) -> Decimal:
        return (self.valor_bruto or Decimal("0")) - (self.taxa_adquirente or Decimal("0"))

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


MAX_COMPANY_LOGO_SIZE = 150 * 1024


def validate_company_logo(file_obj):
    if not file_obj:
        return

    if getattr(file_obj, "size", 0) > MAX_COMPANY_LOGO_SIZE:
        raise ValidationError("Envie uma logo com no maximo 150KB.")

    content_type = getattr(file_obj, "content_type", "")
    if content_type and content_type != "image/png":
        raise ValidationError("Envie a logo em PNG com fundo transparente.")


class Empresa(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    responsavel_nome = models.CharField(max_length=150, blank=True)
    email_contato = models.EmailField(blank=True)
    telefone_contato = models.CharField(max_length=25, blank=True)
    whatsapp = models.CharField(max_length=25, blank=True)
    website = models.URLField(blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=120, blank=True)
    endereco = models.CharField(max_length=255, blank=True)
    descricao_rodape = models.TextField(blank=True)
    cotacao_observacao_padrao = models.TextField(blank=True)
    cotacao_condicoes_gerais = models.TextField(blank=True)
    cotacao_hint_valor_referencia = models.CharField(max_length=180, blank=True)
    cotacao_hint_valor_encontrado = models.CharField(max_length=180, blank=True)
    cotacao_hint_taxa_embarque = models.CharField(max_length=180, blank=True)
    cotacao_hint_valor_total = models.CharField(max_length=180, blank=True)
    cotacao_hint_valor_parcelado = models.CharField(max_length=180, blank=True)
    cotacao_hint_economia = models.CharField(max_length=180, blank=True)
    emissao_observacao_confirmada = models.TextField(blank=True)
    emissao_observacao_pendente = models.TextField(blank=True)
    emissao_orientacoes = models.TextField(blank=True)
    emissao_cta_companhia = models.CharField(max_length=120, blank=True)
    emissao_bagagem_mao_hint = models.CharField(max_length=180, blank=True)
    emissao_bagagem_despachada_hint = models.CharField(max_length=180, blank=True)
    emissao_hint_taxa_embarque = models.CharField(max_length=180, blank=True)
    emissao_hint_taxa_servico = models.CharField(max_length=180, blank=True)
    emissao_hint_valor_total = models.CharField(max_length=180, blank=True)
    logo_documentos = models.FileField(
        upload_to="empresas/logos/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["png"]),
            validate_company_logo,
        ],
        help_text="PNG horizontal com fundo transparente, recomendado 1200x400px e ate 150KB.",
    )
    ocultar_logo_documentos = models.BooleanField(default=False)
    limite_colaboradores = models.PositiveIntegerField(default=0)
    admin = models.OneToOneField(
        "gestao.Cliente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="empresa_administrada",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @staticmethod
    def _clean_multiline_items(raw_value):
        items = []
        for line in (raw_value or "").splitlines():
            cleaned = line.strip().lstrip("-").lstrip("•").strip()
            if cleaned:
                items.append(cleaned)
        return items

    def get_text_list(self, field_name):
        return self._clean_multiline_items(getattr(self, field_name, ""))

    def total_operadores_ativos(self, *, exclude_cliente_id=None):
        queryset = self.pessoas.filter(perfil="operador", ativo=True)
        if exclude_cliente_id:
            queryset = queryset.exclude(pk=exclude_cliente_id)
        return queryset.count()

    def total_clientes_ativos(self):
        return self.pessoas.filter(perfil="cliente", ativo=True).count()

    def vagas_colaboradores(self):
        return max(self.limite_colaboradores - self.total_operadores_ativos(), 0)

    def limite_colaboradores_atingido(self, *, exclude_cliente_id=None):
        return self.total_operadores_ativos(exclude_cliente_id=exclude_cliente_id) >= self.limite_colaboradores

    @property
    def logo_documentos_url(self):
        if not self.logo_documentos:
            return ""
        try:
            logo_name = getattr(self.logo_documentos, "name", "") or ""
            storage = getattr(self.logo_documentos, "storage", None)
            if not logo_name:
                return ""
            if storage and not storage.exists(logo_name):
                return ""
            return self.logo_documentos.url
        except (ValueError, OSError):
            return ""

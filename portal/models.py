import unicodedata

from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone


_CATEGORIA_SLUG_MAP = {
    "milhas": "milhas-e-pontos",
    "milhas e pontos": "milhas-e-pontos",
    "pontos": "milhas-e-pontos",
    "fidelidade": "milhas-e-pontos",
    "cartoes": "cartoes-credito",
    "cartoes de credito": "cartoes-credito",
    "cartao de credito": "cartoes-credito",
    "credito": "cartoes-credito",
    "hoteis": "hoteis-resorts",
    "hoteis e resorts": "hoteis-resorts",
    "resorts": "hoteis-resorts",
    "hotel": "hoteis-resorts",
    "promocoes": "promocoes",
    "promocao": "promocoes",
    "promocoes e ofertas": "promocoes",
    "ofertas": "promocoes",
    "viagens": "viagens",
    "viagem": "viagens",
    "turismo": "viagens",
    "destinos": "viagens",
    "destino": "viagens",
    "roteiro": "viagens",
    "roteiros": "viagens",
}


def _categoria_to_slug(categoria):
    normalized = unicodedata.normalize("NFKD", categoria or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower().strip()
    return _CATEGORIA_SLUG_MAP.get(normalized, "milhas-e-pontos")


class Fonte(models.Model):
    TIPO_COLETA_CHOICES = (
        ("rss", "RSS"),
        ("html", "HTML"),
        ("api", "API"),
    )

    nome = models.CharField(max_length=120, unique=True)
    url = models.URLField()
    ativa = models.BooleanField(default=True)
    tipo_coleta = models.CharField(max_length=20, choices=TIPO_COLETA_CHOICES, default="html")
    categoria_padrao = models.CharField(max_length=80, blank=True)
    parser_key = models.CharField(max_length=80, blank=True)
    headers_json = models.JSONField(default=dict, blank=True)
    confianca_minima = models.DecimalField(max_digits=4, decimal_places=2, default=0.70)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class MateriaBruta(models.Model):
    fonte = models.ForeignKey(Fonte, on_delete=models.CASCADE, related_name="materias_brutas")
    url_original = models.URLField(unique=True)
    titulo_extraido = models.CharField(max_length=300, blank=True)
    html_bruto = models.TextField(blank=True)
    texto_base = models.TextField(blank=True)
    hash_conteudo = models.CharField(max_length=64, db_index=True)
    imagem_url = models.URLField(blank=True)
    data_publicacao_original = models.DateTimeField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    data_coleta = models.DateTimeField(auto_now_add=True)
    processada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-data_coleta"]

    def __str__(self):
        return self.titulo_extraido or self.url_original


class NoticiaPublicada(models.Model):
    STATUS_CHOICES = (
        ("draft", "Rascunho"),
        ("published", "Publicada"),
        ("archived", "Arquivada"),
    )

    materia_bruta = models.OneToOneField(
        MateriaBruta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="noticia_publicada",
    )
    fonte = models.ForeignKey(Fonte, on_delete=models.SET_NULL, null=True, blank=True, related_name="noticias")
    titulo = models.CharField(max_length=220)
    resumo = models.TextField()
    conteudo = models.TextField()
    slug = models.SlugField(unique=True, max_length=240)
    categoria = models.CharField(max_length=80, blank=True)
    topico = models.CharField(max_length=120, blank=True)
    tags_json = models.JSONField(default=list, blank=True)
    imagem = models.FileField(upload_to="portal/noticias/", blank=True, null=True)
    imagem_url = models.URLField(blank=True)
    imagem_ilustrativa = models.BooleanField(default=False)
    url_fonte = models.URLField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    confianca = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    publicada_em = models.DateTimeField(default=timezone.now)
    metadata_json = models.JSONField(default=dict, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-publicada_em", "-criada_em"]
        indexes = [
            models.Index(fields=["status", "-publicada_em"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "categoria", "topico"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.titulo)[:220]
        base_slug = self.slug
        suffix = 2
        while (
            NoticiaPublicada.objects.exclude(pk=self.pk)
            .filter(slug=self.slug)
            .exists()
        ):
            truncated = base_slug[: max(1, 220 - len(str(suffix)) - 1)]
            self.slug = f"{truncated}-{suffix}"
            suffix += 1
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        categoria_slug = _categoria_to_slug(self.categoria)
        return reverse("portal_noticia_detalhe", kwargs={"categoria_slug": categoria_slug, "slug": self.slug})

    @property
    def imagem_exibicao(self):
        if self.imagem:
            return self.imagem.url
        return self.imagem_url

    @property
    def tags_exibicao(self):
        excluded = {
            (self.categoria or "").strip().lower(),
            (self.topico or "").strip().lower(),
        }
        return [
            tag.strip()
            for tag in (self.tags_json or [])
            if isinstance(tag, str) and tag.strip() and tag.strip().lower() not in excluded
        ][:5]

    def __str__(self):
        return self.titulo


class JobExecucao(models.Model):
    STATUS_CHOICES = (
        ("running", "Executando"),
        ("success", "Sucesso"),
        ("partial", "Parcial"),
        ("failed", "Falhou"),
    )

    job_name = models.CharField(max_length=120, default="sync_home_news")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    horario = models.DateTimeField(default=timezone.now)
    finalizado_em = models.DateTimeField(null=True, blank=True)
    erro = models.TextField(blank=True)
    quantidade_processada = models.PositiveIntegerField(default=0)
    quantidade_publicada = models.PositiveIntegerField(default=0)
    metadata_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-horario"]

    def __str__(self):
        return f"{self.job_name} - {self.get_status_display()} - {self.horario:%d/%m/%Y %H:%M}"


class PortalMetricDaily(models.Model):
    METRIC_TYPE_CHOICES = (
        ("page_view", "Page View"),
        ("click", "Click"),
    )

    metric_date = models.DateField(db_index=True)
    site_environment = models.CharField(max_length=20, default="local", db_index=True)
    site_host = models.CharField(max_length=120, blank=True, db_index=True)
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPE_CHOICES, db_index=True)
    path = models.CharField(max_length=255, blank=True, db_index=True)
    event_name = models.CharField(max_length=80, blank=True, db_index=True)
    section = models.CharField(max_length=80, blank=True)
    article_slug = models.CharField(max_length=240, blank=True, db_index=True)
    article_category = models.CharField(max_length=120, blank=True)
    article_topic = models.CharField(max_length=120, blank=True)
    total = models.PositiveIntegerField(default=0)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-metric_date", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "metric_date",
                    "site_environment",
                    "site_host",
                    "metric_type",
                    "path",
                    "event_name",
                    "section",
                    "article_slug",
                    "article_category",
                    "article_topic",
                ],
                name="portal_metric_daily_unique_bucket_env",
            )
        ]

    def __str__(self):
        return f"{self.metric_date} {self.metric_type} {self.path or self.event_name} ({self.total})"


class LeadPlataforma(models.Model):
    STATUS_CHOICES = (
        ("novo", "Novo"),
        ("contatado", "Contatado"),
        ("qualificado", "Qualificado"),
        ("arquivado", "Arquivado"),
    )

    EQUIPE_TAMANHO_CHOICES = (
        ("1-2", "1 a 2 pessoas"),
        ("3-5", "3 a 5 pessoas"),
        ("6-10", "6 a 10 pessoas"),
        ("11-20", "11 a 20 pessoas"),
        ("21+", "Mais de 20 pessoas"),
    )

    nome_completo = models.CharField(max_length=180)
    empresa = models.CharField(max_length=180)
    cargo = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    telefone = models.CharField(max_length=40)
    equipe_tamanho = models.CharField(
        max_length=20,
        choices=EQUIPE_TAMANHO_CHOICES,
        blank=True,
    )
    mensagem = models.TextField(blank=True)
    aceite_versao = models.CharField(max_length=40, blank=True)
    aceito_em = models.DateTimeField(null=True, blank=True)
    aceito_ip = models.CharField(max_length=45, blank=True)
    aceito_user_agent = models.CharField(max_length=255, blank=True)
    source_environment = models.CharField(max_length=20, default="local", db_index=True)
    source_host = models.CharField(max_length=120, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="novo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.nome_completo} - {self.empresa}"


class LeadAlertaEmail(models.Model):
    STATUS_ATIVO = "ativo"
    STATUS_PAUSADO = "pausado"
    STATUS_DESCADASTRADO = "descadastrado"
    STATUS_CHOICES = (
        (STATUS_ATIVO, "Ativo"),
        (STATUS_PAUSADO, "Pausado"),
        (STATUS_DESCADASTRADO, "Descadastrado"),
    )

    MOTIVO_CANCELAMENTO_MUITOS_EMAILS = "muitos_emails"
    MOTIVO_CANCELAMENTO_CONTEUDO_IRRELEVANTE = "conteudo_irrelevante"
    MOTIVO_CANCELAMENTO_SEM_INTERESSE = "sem_interesse"
    MOTIVO_CANCELAMENTO_NAO_RECONHECE = "nao_reconhece_cadastro"
    MOTIVO_CANCELAMENTO_CAIXA_CHEIA = "caixa_cheia"
    MOTIVO_CANCELAMENTO_CHOICES = (
        (MOTIVO_CANCELAMENTO_MUITOS_EMAILS, "Recebo muitos e-mails"),
        (MOTIVO_CANCELAMENTO_CONTEUDO_IRRELEVANTE, "O conteudo nao e relevante para mim"),
        (MOTIVO_CANCELAMENTO_SEM_INTERESSE, "Nao tenho mais interesse nos alertas"),
        (MOTIVO_CANCELAMENTO_NAO_RECONHECE, "Nao lembro de ter me cadastrado"),
        (MOTIVO_CANCELAMENTO_CAIXA_CHEIA, "Quero reduzir mensagens na caixa de entrada"),
    )

    ORIGEM_HOME = "home"
    ORIGEM_ALERTAS = "alertas"
    ORIGEM_CHOICES = (
        (ORIGEM_HOME, "Home"),
        (ORIGEM_ALERTAS, "Página de alertas"),
    )

    nome_completo = models.CharField(max_length=180)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=40)
    origem_cadastro = models.CharField(
        max_length=20,
        choices=ORIGEM_CHOICES,
        default=ORIGEM_ALERTAS,
    )
    aceite_versao = models.CharField(max_length=40, blank=True)
    aceito_em = models.DateTimeField(null=True, blank=True)
    aceito_ip = models.CharField(max_length=45, blank=True)
    aceito_user_agent = models.CharField(max_length=255, blank=True)
    source_environment = models.CharField(max_length=20, default="local", db_index=True)
    source_host = models.CharField(max_length=120, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVO)
    motivo_cancelamento = models.CharField(
        max_length=40,
        choices=MOTIVO_CANCELAMENTO_CHOICES,
        blank=True,
    )
    cancelado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Lead de alertas por e-mail"
        verbose_name_plural = "Leads de alertas por e-mail"

    def __str__(self):
        return f"{self.nome_completo} - {self.email}"


class AlertEmailDigestItem(models.Model):
    KIND_NEW = "new"
    KIND_UPDATED = "updated"
    KIND_CHOICES = (
        (KIND_NEW, "Novo alerta"),
        (KIND_UPDATED, "Alerta atualizado"),
    )

    alerta = models.ForeignKey(
        "gestao.AlertaViagem",
        on_delete=models.CASCADE,
        related_name="alert_email_digest_items",
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_NEW)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        route_label = (self.metadata_json or {}).get("route_label") or f"Alerta #{self.alerta_id}"
        return f"{self.get_kind_display()} - {route_label}"

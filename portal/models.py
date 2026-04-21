import hashlib
import secrets
import unicodedata
import uuid

from django.contrib.auth.hashers import check_password, make_password
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
    aceito_url_origem = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="URL absoluta onde o aceite foi registrado (evidencia forense LGPD)",
    )
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
    aceito_url_origem = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="URL absoluta onde o aceite foi registrado (evidencia forense LGPD)",
    )
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


class ModuloEstudo(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    slug = models.SlugField(max_length=220, unique=True)
    icone = models.CharField(max_length=50, blank=True, help_text="Nome do ícone (ex: book, star, plane)")
    cor = models.CharField(max_length=7, default="#2563eb", help_text="Cor hex do módulo")
    ordem = models.PositiveIntegerField(default=0, db_index=True)
    ativo = models.BooleanField(default=True, db_index=True)
    destaque_home = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Se marcado, aparece como módulo de amostra aberto na home pública (apenas 1 deve ficar marcado)",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Módulo de estudo"
        verbose_name_plural = "Módulos de estudo"
        ordering = ["ordem", "titulo"]

    def __str__(self):
        return self.titulo

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("portal_modulo_detalhe", kwargs={"slug": self.slug})


class ArtigoEstudo(models.Model):
    STATUS_CHOICES = [
        ("draft", "Rascunho"),
        ("published", "Publicado"),
        ("archived", "Arquivado"),
    ]

    modulo = models.ForeignKey(ModuloEstudo, on_delete=models.CASCADE, related_name="artigos")
    titulo = models.CharField(max_length=220)
    resumo = models.TextField(help_text="Resumo curto para exibição em cards")
    conteudo = models.TextField(help_text="Conteúdo HTML completo do artigo")
    slug = models.SlugField(max_length=240, unique=True)
    imagem = models.FileField(upload_to="portal/artigos/", blank=True, null=True)
    imagem_url = models.URLField(blank=True)
    autor = models.CharField(max_length=120, default="Redação NC Fly")
    tempo_leitura = models.PositiveIntegerField(default=5, help_text="Tempo de leitura em minutos")
    ordem = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    seo_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    keywords_json = models.JSONField(default=list, blank=True)
    youtube_search_terms_json = models.JSONField(default=list, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    ia_revisao_json = models.JSONField(default=dict, blank=True)
    publicado_em = models.DateTimeField(null=True, blank=True)
    notificado_em = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Quando as notificacoes de artigo novo foram disparadas para os inscritos "
            "(OptInArtigoNovo). Null = ainda nao enviado."
        ),
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Artigo de estudo"
        verbose_name_plural = "Artigos de estudo"
        ordering = ["modulo__ordem", "ordem", "titulo"]
        indexes = [
            models.Index(fields=["status", "-publicado_em"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["modulo", "ordem"]),
        ]

    def __str__(self):
        return self.titulo

    @property
    def imagem_exibicao(self):
        if self.imagem:
            return self.imagem.url
        return self.imagem_url or ""

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("portal_artigo_detalhe", kwargs={"modulo_slug": self.modulo.slug, "slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.template.defaultfilters import slugify
            base = slugify(self.titulo)
            slug = base
            n = 1
            while ArtigoEstudo.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        if self.conteudo:
            from portal.services.html_sanitizer import sanitize_article_html
            self.conteudo = sanitize_article_html(self.conteudo)
        super().save(*args, **kwargs)


class ArtigoVideoYoutube(models.Model):
    artigo = models.ForeignKey(ArtigoEstudo, on_delete=models.CASCADE, related_name="videos")
    video_id = models.CharField(max_length=20)
    titulo = models.CharField(max_length=300)
    descricao = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    canal = models.CharField(max_length=200, blank=True)
    duracao = models.CharField(max_length=20, blank=True, help_text="Ex: 12:34")
    visualizacoes = models.PositiveIntegerField(default=0)
    termo_busca = models.CharField(max_length=200, blank=True)
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True, db_index=True)
    buscado_em = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "Vídeo do YouTube (artigo)"
        verbose_name_plural = "Vídeos do YouTube (artigos)"
        ordering = ["ordem", "-visualizacoes"]
        constraints = [
            models.UniqueConstraint(fields=["artigo", "video_id"], name="unique_artigo_video"),
        ]

    def __str__(self):
        return f"{self.titulo} ({self.video_id})"

    @property
    def youtube_url(self):
        return f"https://www.youtube.com/watch?v={self.video_id}"


# ---------------------------------------------------------------------------
# Portal B2C — autenticacao isolada do SaaS B2B (nao usa auth.User do Django)
# ---------------------------------------------------------------------------


def _gen_unsubscribe_token() -> str:
    return secrets.token_urlsafe(32)


class PortalUser(models.Model):
    """Conta de usuario do Portal B2C (notícias/alertas/artigos).

    Totalmente isolada de `auth.User`:
    - nao tem `is_staff`, `is_superuser`, grupos nem permissoes Django
    - nao pode logar no SaaS B2B nem no Admin
    - senha gravada via Django PBKDF2 (`make_password`) — mesmo algoritmo do
      `auth.User`, mas sem acoplamento de tabela
    - identificada pela sessao Django via chave `portal_user_id`
    """

    email = models.EmailField(unique=True, db_index=True)
    nome = models.CharField(max_length=180, blank=True)
    senha_hash = models.CharField(max_length=256, blank=True, default="")
    google_sub = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Google account 'sub' (ID estavel) — unico por usuario Google",
    )
    email_verificado = models.BooleanField(default=False, db_index=True)
    ativo = models.BooleanField(default=True, db_index=True)

    ip_cadastro = models.CharField(max_length=45, blank=True, default="")
    user_agent_cadastro = models.CharField(max_length=255, blank=True, default="")
    source_environment = models.CharField(max_length=20, default="local", db_index=True)
    source_host = models.CharField(max_length=120, blank=True, db_index=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    ultimo_login_em = models.DateTimeField(null=True, blank=True)
    ultimo_login_ip = models.CharField(max_length=45, blank=True, default="")

    class Meta:
        verbose_name = "Usuario do portal B2C"
        verbose_name_plural = "Usuarios do portal B2C"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["google_sub"],
                name="unique_portal_user_google_sub",
                condition=models.Q(google_sub__gt=""),
            ),
        ]

    def __str__(self):
        return self.email

    # ------------------------------------------------------------------
    # Senha — PBKDF2 via django.contrib.auth.hashers
    # ------------------------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        self.senha_hash = make_password(raw_password) if raw_password else ""

    def check_password(self, raw_password: str) -> bool:
        if not self.senha_hash or not raw_password:
            return False
        return check_password(raw_password, self.senha_hash)

    def has_password(self) -> bool:
        return bool(self.senha_hash)

    # ------------------------------------------------------------------
    # Identidade para views (equivale a request.user.is_authenticated)
    # ------------------------------------------------------------------
    @property
    def is_authenticated(self) -> bool:
        return self.ativo

    def marcar_login(self, ip: str = "") -> None:
        self.ultimo_login_em = timezone.now()
        if ip:
            self.ultimo_login_ip = ip[:45]
        self.save(update_fields=["ultimo_login_em", "ultimo_login_ip", "atualizado_em"])


class _OptInBase(models.Model):
    """Base abstrata para opt-ins granulares do Portal B2C.

    Cada tipo de opt-in vira tabela separada (ex.: alertas de passagens,
    notificacao de artigos). Isso garante que `unsubscribe` em um canal NAO
    afeta os outros (LGPD — consentimento granular e revogavel por canal).
    """

    user = models.ForeignKey(
        PortalUser,
        on_delete=models.CASCADE,
        related_name="+",
    )
    email = models.EmailField(db_index=True)
    ativo = models.BooleanField(default=True, db_index=True)
    token_unsubscribe = models.CharField(
        max_length=64,
        unique=True,
        default=_gen_unsubscribe_token,
    )

    # Evidencia do consentimento — LGPD art. 8
    aceite_versao = models.CharField(max_length=40, blank=True, default="")
    aceite_hash_documento = models.CharField(max_length=64, blank=True, default="")
    aceito_em = models.DateTimeField(null=True, blank=True)
    aceito_ip = models.CharField(max_length=45, blank=True, default="")
    aceito_user_agent = models.CharField(max_length=255, blank=True, default="")
    aceito_url_origem = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="URL absoluta onde o opt-in foi registrado (evidencia forense LGPD)",
    )

    cancelado_em = models.DateTimeField(null=True, blank=True)
    cancelado_ip = models.CharField(max_length=45, blank=True, default="")
    motivo_cancelamento = models.CharField(max_length=80, blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-criado_em"]

    def cancelar(self, *, ip: str = "", motivo: str = "") -> None:
        self.ativo = False
        self.cancelado_em = timezone.now()
        self.cancelado_ip = (ip or "")[:45]
        self.motivo_cancelamento = (motivo or "")[:80]
        self.save(
            update_fields=[
                "ativo",
                "cancelado_em",
                "cancelado_ip",
                "motivo_cancelamento",
                "atualizado_em",
            ]
        )


class OptInAlertaPassagem(_OptInBase):
    """Opt-in para receber alertas de passagens (precos/milhas) por email."""

    class Meta(_OptInBase.Meta):
        verbose_name = "Opt-in de alerta de passagem"
        verbose_name_plural = "Opt-ins de alertas de passagens"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                name="unique_optin_alerta_passagem_por_user",
            ),
        ]

    def __str__(self):
        return f"Alertas passagem — {self.email} ({'ativo' if self.ativo else 'cancelado'})"


class OptInArtigoNovo(_OptInBase):
    """Opt-in para receber notificacao quando um novo artigo/noticia for publicado."""

    class Meta(_OptInBase.Meta):
        verbose_name = "Opt-in de artigo novo"
        verbose_name_plural = "Opt-ins de artigos novos"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                name="unique_optin_artigo_novo_por_user",
            ),
        ]

    def __str__(self):
        return f"Artigos — {self.email} ({'ativo' if self.ativo else 'cancelado'})"


def _documento_hash(conteudo: str) -> str:
    return hashlib.sha256((conteudo or "").encode("utf-8")).hexdigest()


class ProgressoArtigo(models.Model):
    """Progresso de leitura de um `ArtigoEstudo` por um `PortalUser`.

    Isolado do SaaS B2B — referencia somente o `PortalUser`. Uma linha por
    par (user, artigo). Usado para:
    - montar barra de progresso por modulo (X de N artigos lidos)
    - mostrar quais artigos ja foram lidos na lista do modulo
    - permitir retomar leitura
    """

    user = models.ForeignKey(
        PortalUser,
        on_delete=models.CASCADE,
        related_name="progressos_artigo",
    )
    artigo = models.ForeignKey(
        ArtigoEstudo,
        on_delete=models.CASCADE,
        related_name="progressos",
    )
    lido_em = models.DateTimeField(null=True, blank=True, db_index=True)
    primeira_visita_em = models.DateTimeField(auto_now_add=True)
    ultima_visita_em = models.DateTimeField(auto_now=True)
    progresso_percentual = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Progresso de artigo"
        verbose_name_plural = "Progressos de artigos"
        ordering = ["-ultima_visita_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "artigo"],
                name="unique_progresso_user_artigo",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "artigo"]),
            models.Index(fields=["user", "lido_em"]),
        ]

    def __str__(self):
        status = "lido" if self.lido_em else f"{self.progresso_percentual}%"
        return f"{self.user.email} — {self.artigo.titulo} ({status})"

    @property
    def concluido(self) -> bool:
        return bool(self.lido_em) or self.progresso_percentual >= 100

    def marcar_como_lido(self) -> None:
        """Seta `lido_em=now()` e `progresso_percentual=100`."""
        now = timezone.now()
        self.lido_em = now
        self.progresso_percentual = 100
        # `ultima_visita_em` é auto_now — atualizado no save()
        self.save(
            update_fields=[
                "lido_em",
                "progresso_percentual",
                "ultima_visita_em",
            ]
        )


def criar_opt_ins_no_cadastro(
    user: PortalUser,
    *,
    ip: str,
    user_agent: str,
    versao_termos: str = "",
    hash_termos: str = "",
    url_origem: str = "",
):
    """Cria (ou reativa) os 2 opt-ins obrigatorios no cadastro.

    Retorna tupla (opt_alerta, opt_artigo) — ambos `ativo=True` quando o
    cadastro foi bem-sucedido. Evidencia de consentimento (IP/UA/timestamp/
    URL de origem/versao+hash dos termos) e gravada no proprio opt-in, em
    linha com o modelo `AceiteDocumentoPlataforma` do SaaS.
    """

    now = timezone.now()
    base = {
        "email": user.email,
        "aceite_versao": versao_termos,
        "aceite_hash_documento": hash_termos,
        "aceito_em": now,
        "aceito_ip": (ip or "")[:45],
        "aceito_user_agent": (user_agent or "")[:255],
        "aceito_url_origem": (url_origem or "")[:500],
        "ativo": True,
    }

    opt_alerta, _ = OptInAlertaPassagem.objects.update_or_create(
        user=user,
        defaults={**base, "cancelado_em": None, "cancelado_ip": "", "motivo_cancelamento": ""},
    )
    opt_artigo, _ = OptInArtigoNovo.objects.update_or_create(
        user=user,
        defaults={**base, "cancelado_em": None, "cancelado_ip": "", "motivo_cancelamento": ""},
    )
    return opt_alerta, opt_artigo


# ---------------------------------------------------------------------------
# PreUser — tracking de visitantes anonimos (conversao)
# ---------------------------------------------------------------------------
#
# Registra todo visitante do portal publico via cookie `pu_uid` (UUID v4).
# Linkado ao `PortalUser` no login/cadastro — permite medir taxa de conversao,
# tempo ate converter, UTMs que converteram melhor, etc.
#
# LGPD: cookie tecnico de legitimo interesse (funcional, nao rastreia entre
# dominios). Nao precisa consent banner, mas precisa estar descrito na
# politica de privacidade. Em pedidos de exclusao (art. 18), excluir tambem
# os PreUsers linkados ao PortalUser.
#
# Metrica sugerida para dashboard do ncadm:
#   - total de pre_users (criados, ativos ultimos 7/30 dias)
#   - convertidos no periodo / total -> taxa de conversao
#   - breakdown por utm_source / utm_campaign
class PreUser(models.Model):
    """Visitante anonimo do portal — identificado por cookie `pu_uid`.

    Criado na primeira visita, atualizado a cada hit (throttled para evitar
    N UPDATEs/segundo) e linkado ao `PortalUser` quando o visitante faz
    login ou se cadastra.
    """

    uid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)

    # --- primeiro acesso (nao muda depois) ---
    primeiro_ip = models.GenericIPAddressField(null=True, blank=True)
    primeiro_ua = models.TextField(blank=True)
    primeira_url = models.URLField(max_length=500, blank=True)
    primeiro_referrer = models.URLField(max_length=500, blank=True)
    utm_source = models.CharField(max_length=120, blank=True)
    utm_medium = models.CharField(max_length=120, blank=True)
    utm_campaign = models.CharField(max_length=120, blank=True)

    # --- ultimo acesso (atualizado, com throttle) ---
    ultimo_ip = models.GenericIPAddressField(null=True, blank=True)
    ultima_url = models.URLField(max_length=500, blank=True)
    ultima_visita_em = models.DateTimeField(auto_now=True)

    total_visitas = models.PositiveIntegerField(default=1)

    # --- conversao ---
    convertido_em = models.DateTimeField(null=True, blank=True)
    portal_user = models.ForeignKey(
        "PortalUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pre_users",
    )

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Pre-user (visitante anonimo)"
        verbose_name_plural = "Pre-users (visitantes anonimos)"
        indexes = [
            models.Index(fields=["portal_user", "convertido_em"]),
            models.Index(fields=["-criado_em"]),
        ]

    def __str__(self):
        if self.portal_user_id:
            return f"PreUser {self.uid} -> {self.portal_user_id}"
        return f"PreUser {self.uid} (anon)"


# ---------------------------------------------------------------------------
# ComentarioArtigo — sistema de comentarios com moderacao e evidencia legal
# ---------------------------------------------------------------------------
#
# Regras de negocio:
#   - So usuario logado (PortalUser) comenta
#   - Janela de 15min pra autor editar OU excluir
#   - Apos 15min: soft delete so via superadmin (oculto_admin)
#   - Superadmin nao edita corpo, so oculta/restaura
#   - Resposta a resposta vira resposta ao comentario raiz (max 1 nivel)
#
# Evidencia legal (Marco Civil + LGPD):
#   - Snapshot de email/nome sobrevive a exclusao de conta (defesa juridica)
#   - SHA-256 do corpo prova imutabilidade apos moderacao
#   - IP + user-agent gravados (Marco Civil art. 13 — 6 meses minimo)
#   - Historico de edicoes preservado pra auditoria
#   - Retencao: soft delete permanente (storage barato vs risco juridico)
EDIT_JANELA_MINUTOS = 15


class ComentarioArtigo(models.Model):
    """Comentario publico em ArtigoEstudo — B2C logado."""

    STATUS_PUBLICADO = "publicado"
    STATUS_OCULTO_ADMIN = "oculto_admin"
    STATUS_EXCLUIDO_AUTOR = "excluido_autor"
    STATUS_CHOICES = [
        (STATUS_PUBLICADO, "Publicado"),
        (STATUS_OCULTO_ADMIN, "Oculto pelo admin"),
        (STATUS_EXCLUIDO_AUTOR, "Excluido pelo autor"),
    ]

    # --- Relacoes ---
    artigo = models.ForeignKey(
        ArtigoEstudo,
        on_delete=models.PROTECT,
        related_name="comentarios",
        db_index=True,
    )
    autor = models.ForeignKey(
        PortalUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="comentarios",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="respostas",
    )

    # --- Snapshot do autor (sobrevive a exclusao de conta — evidencia legal) ---
    autor_email_snapshot = models.EmailField(max_length=254)
    autor_nome_snapshot = models.CharField(max_length=180, blank=True)
    exibir_nome_completo = models.BooleanField(
        default=False,
        help_text=(
            "False = email mascarado (ped***@gmail.com). True = nome. "
            "Default False por privacidade."
        ),
    )

    # --- Conteudo ---
    corpo = models.TextField(max_length=2000)
    corpo_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 do corpo publicado — prova de imutabilidade.",
    )

    # --- Moderacao / status ---
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PUBLICADO,
        db_index=True,
    )
    ocultado_por = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="comentarios_ocultados",
    )
    ocultado_em = models.DateTimeField(null=True, blank=True)
    motivo_ocultacao = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Motivo do admin ao ocultar — defesa juridica.",
    )

    # --- Edicao (autor, janela 15min) ---
    editado = models.BooleanField(default=False)
    editado_em = models.DateTimeField(null=True, blank=True)
    historico_edicoes = models.JSONField(
        default=list, blank=True,
        help_text=(
            "Lista de versoes anteriores: "
            "[{corpo, corpo_hash, editado_em_iso}, ...]. Defesa legal."
        ),
    )

    # --- Exclusao pelo autor (janela 15min) ---
    excluido_em = models.DateTimeField(null=True, blank=True)

    # --- Evidencia legal ---
    ip_cadastro = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    # --- Timestamps ---
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Comentario de artigo"
        verbose_name_plural = "Comentarios de artigos"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["artigo", "status", "-criado_em"]),
            models.Index(fields=["parent", "-criado_em"]),
            models.Index(fields=["autor_email_snapshot", "-criado_em"]),
        ]

    def __str__(self):
        return f"Comentario #{self.pk} em {self.artigo_id} ({self.status})"

    # ---- helpers ----
    @staticmethod
    def calcular_hash(corpo: str) -> str:
        return hashlib.sha256((corpo or "").encode("utf-8")).hexdigest()

    @property
    def dentro_janela_edicao(self) -> bool:
        """Autor pode editar/excluir nos primeiros 15 minutos."""
        if not self.criado_em:
            return False
        limite = self.criado_em + timezone.timedelta(minutes=EDIT_JANELA_MINUTOS)
        return timezone.now() <= limite

    @property
    def nome_exibicao(self) -> str:
        """Nome completo (se optou) ou email mascarado."""
        if self.exibir_nome_completo and self.autor_nome_snapshot:
            return self.autor_nome_snapshot
        return self._mascarar_email(self.autor_email_snapshot)

    @staticmethod
    def _mascarar_email(email: str) -> str:
        """`pedrinho@gmail.com` -> `ped***@gmail.com`."""
        if not email or "@" not in email:
            return "anonimo"
        local, domain = email.split("@", 1)
        if len(local) <= 3:
            mascara = local[:1] + "***"
        else:
            mascara = local[:3] + "***"
        return f"{mascara}@{domain}"

    @property
    def inicial_avatar(self) -> str:
        """Primeira letra do nome ou do email."""
        fonte = self.autor_nome_snapshot or self.autor_email_snapshot or "?"
        fonte = fonte.strip()
        return fonte[0].upper() if fonte else "?"

    @property
    def is_publicado(self) -> bool:
        return self.status == self.STATUS_PUBLICADO

    def aplicar_snapshot_autor(self) -> None:
        """Copia email/nome do autor pra campos snapshot (antes de salvar)."""
        if self.autor:
            if not self.autor_email_snapshot:
                self.autor_email_snapshot = self.autor.email
            if not self.autor_nome_snapshot:
                self.autor_nome_snapshot = (self.autor.nome or "").strip()

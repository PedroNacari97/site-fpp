from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone


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
        return reverse("portal_noticia_detalhe", kwargs={"slug": self.slug})

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

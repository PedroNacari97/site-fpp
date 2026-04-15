"""Catálogo de marcas consumido pelo gerador de imagens (portal/services/ai_pipeline).

Fonte dos dados: o CSV ``marcas_api_brandfetch_v2.csv`` (seed) é importado uma
vez para este model via ``manage.py import_marcas_catalogo``. Depois o
``portal/services/brand_catalog.py`` lê direto daqui.
"""
from django.db import models


class MarcaCatalogo(models.Model):
    NICHO_BANCOS = "Bancos"
    NICHO_FIDELIDADE = "Programas Fidelidade"
    NICHO_CARTOES = "Cartoes"
    NICHO_AEREAS = "Companhias Aereas"
    NICHO_HOTEIS = "Hoteis"
    NICHO_OTA = "OTAs/Viagens"
    NICHO_OUTROS = "Outros"

    nome = models.CharField(max_length=120, unique=True)
    nicho = models.CharField(max_length=80, blank=True, db_index=True)
    dominio = models.CharField(max_length=120, blank=True)
    cor_hex = models.CharField(max_length=9, default="#000000")
    logo_url = models.URLField(max_length=600, blank=True)
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Lista de termos (lowercase) usados para detectar a marca no texto. "
            "Se vazio, o pipeline gera a partir do nome/dominio."
        ),
    )
    ativo = models.BooleanField(default=True, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Marca (catalogo)"
        verbose_name_plural = "Marcas (catalogo)"
        ordering = ["nicho", "nome"]

    def __str__(self):
        return self.nome

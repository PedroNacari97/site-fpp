"""Busca logos via Clearbit e cria/atualiza registros BrandVisual.

Uso:
    from portal.services.brand_seeder import seed_all_brands, get_or_create_brand_from_title

    seed_all_brands()                        # popula todas as marcas
    brand = get_or_create_brand_from_title("LATAM Pass oferece bonus")
"""
from __future__ import annotations

import logging
from io import BytesIO

import requests
from colorthief import ColorThief
from django.core.files.base import ContentFile

from gestao.models import BrandVisual

logger = logging.getLogger(__name__)

CLEARBIT_URL = "https://logo.clearbit.com/"

# (slug, domain) — usado para buscar logo e criar BrandVisual
BRANDS: dict[str, tuple[str, str]] = {
    # Companhias Aereas
    "latam-airlines":       ("LATAM Airlines",       "latam.com"),
    "gol":                  ("GOL",                  "voegol.com.br"),
    "azul-airlines":        ("Azul Airlines",        "voeazul.com.br"),
    "avianca":              ("Avianca",              "avianca.com"),
    "tap-air-portugal":     ("TAP Air Portugal",     "flytap.com"),
    "emirates":             ("Emirates",             "emirates.com"),
    "qatar-airways":        ("Qatar Airways",        "qatarairways.com"),
    "lufthansa":            ("Lufthansa",            "lufthansa.com"),
    "united-airlines":      ("United Airlines",      "united.com"),
    "delta":                ("Delta",                "delta.com"),
    "american-airlines":    ("American Airlines",    "aa.com"),
    "british-airways":      ("British Airways",      "britishairways.com"),
    "copa-airlines":        ("Copa Airlines",        "copaair.com"),
    "turkish-airlines":     ("Turkish Airlines",     "turkishairlines.com"),
    "klm":                  ("KLM",                  "klm.com"),
    "iberia":               ("Iberia",               "iberia.com"),
    "swiss":                ("Swiss",                "swiss.com"),
    # Programas de Fidelidade
    "latam-pass":           ("LATAM Pass",           "latampass.latam.com"),
    "smiles":               ("Smiles",               "smiles.com.br"),
    "azul-fidelidade":      ("Azul Fidelidade",      "pontos.voeazul.com.br"),
    "livelo":               ("Livelo",               "livelo.com.br"),
    "esfera":               ("Esfera",               "esfera.com.vc"),
    "dotz":                 ("Dotz",                 "dotz.com.br"),
    "premmia":              ("Premmia",              "premmia.com.br"),
    # Bancos
    "nubank":               ("Nubank",               "nubank.com.br"),
    "itau":                 ("Itau",                 "itau.com.br"),
    "bradesco":             ("Bradesco",             "bradesco.com.br"),
    "santander":            ("Santander",            "santander.com.br"),
    "banco-do-brasil":      ("Banco do Brasil",      "bb.com.br"),
    "caixa-economica":      ("Caixa Economica",      "caixa.gov.br"),
    "inter":                ("Inter",                "inter.co"),
    "c6-bank":              ("C6 Bank",              "c6bank.com.br"),
    "btg-pactual":          ("BTG Pactual",          "btgpactual.com"),
    "xp-investimentos":     ("XP Investimentos",     "xpi.com.br"),
    # Cartoes
    "american-express":     ("American Express",     "americanexpress.com"),
    "mastercard":           ("Mastercard",           "mastercard.com"),
    "visa":                 ("Visa",                 "visa.com"),
    "elo":                  ("Elo",                  "elo.com.br"),
    # Hoteis
    "marriott-bonvoy":      ("Marriott Bonvoy",      "marriott.com"),
    "hilton":               ("Hilton",               "hilton.com"),
    "hyatt":                ("Hyatt",                "hyatt.com"),
    "ihg":                  ("IHG",                  "ihg.com"),
    "accor-all":            ("Accor ALL",            "all.accor.com"),
    # OTAs / Viagens
    "booking":              ("Booking.com",          "booking.com"),
    "airbnb":               ("Airbnb",               "airbnb.com"),
    "decolar":              ("Decolar",              "decolar.com"),
    "maxmilhas":            ("Maxmilhas",            "maxmilhas.com.br"),
}


def extract_dominant_color(image_bytes: bytes) -> str:
    """Extrai a cor dominante da imagem e retorna como 'rgb(r,g,b)'."""
    try:
        ct = ColorThief(BytesIO(image_bytes))
        r, g, b = ct.get_color(quality=1)
        return f"rgb({r},{g},{b})"
    except Exception as exc:
        logger.warning("Falha ao extrair cor dominante: %s", exc)
        return "rgb(0,0,0)"


def create_brand_visual(slug: str, domain: str) -> BrandVisual | None:
    """Busca logo no Clearbit e cria/atualiza um BrandVisual."""
    name = BRANDS.get(slug, (slug, domain))[0]
    logo_url = f"{CLEARBIT_URL}{domain}"

    try:
        resp = requests.get(logo_url, timeout=15)
        resp.raise_for_status()
        image_bytes = resp.content
    except requests.RequestException as exc:
        logger.warning("Falha ao baixar logo de %s: %s", domain, exc)
        return None

    primary_color = extract_dominant_color(image_bytes)

    brand, created = BrandVisual.objects.update_or_create(
        slug=slug,
        defaults={
            "name": name,
            "primary_color": primary_color,
            "visual_description": f"Logo da marca {name}",
        },
    )

    # Salva o logo como arquivo
    filename = f"{slug}.png"
    brand.logo.save(filename, ContentFile(image_bytes), save=True)

    action = "Criado" if created else "Atualizado"
    logger.info("%s BrandVisual: %s (cor: %s)", action, name, primary_color)
    return brand


def seed_all_brands() -> list[BrandVisual]:
    """Itera todas as marcas do dicionario BRANDS e cria/atualiza BrandVisual."""
    results = []
    for slug, (name, domain) in BRANDS.items():
        brand = create_brand_visual(slug, domain)
        if brand:
            results.append(brand)
    logger.info("Seed concluido: %d/%d marcas processadas", len(results), len(BRANDS))
    return results


def get_or_create_brand_from_title(title: str) -> BrandVisual | None:
    """Tenta encontrar uma marca correspondente no titulo do artigo/alerta.

    Busca por correspondencia de nome no titulo. Se encontrar e o
    BrandVisual ainda nao existir, cria via Clearbit.
    """
    title_lower = title.lower()

    # Primeiro tenta encontrar no banco
    for brand in BrandVisual.objects.all():
        if brand.name.lower() in title_lower:
            return brand

    # Se nao encontrou no banco, tenta no dicionario BRANDS
    for slug, (name, domain) in BRANDS.items():
        if name.lower() in title_lower:
            return create_brand_visual(slug, domain)

    return None

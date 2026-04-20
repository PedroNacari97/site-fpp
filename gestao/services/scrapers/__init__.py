from .base import ResultadoScrape, Scraper, ScraperError, get_scraper, register_scraper
from .azul import AzulScraper
from .latam import LatamScraper

__all__ = [
    "ResultadoScrape",
    "Scraper",
    "ScraperError",
    "get_scraper",
    "register_scraper",
    "AzulScraper",
    "LatamScraper",
]

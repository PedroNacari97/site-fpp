from urllib.parse import urlparse

from .html import HtmlFetcher, MelhoresCartoesFetcher, PassageiroDePrimeiraFetcher
from .rss import RssFetcher


FETCHER_MAP = {
    "html": HtmlFetcher,
    "rss": RssFetcher,
    "passageirodeprimeira": PassageiroDePrimeiraFetcher,
    "melhorescartoes": MelhoresCartoesFetcher,
    # parser_key aliases
    "feed": RssFetcher,
}


def get_fetcher_for_source(source):
    parser_key = getattr(source, "parser_key", "") or ""
    if parser_key and parser_key in FETCHER_MAP:
        return FETCHER_MAP[parser_key]()

    domain = urlparse(source.url).netloc.lower()
    if "passageirodeprimeira.com" in domain:
        return PassageiroDePrimeiraFetcher()
    if "melhorescartoes.com.br" in domain:
        return MelhoresCartoesFetcher()

    fetcher_cls = FETCHER_MAP.get(source.tipo_coleta, HtmlFetcher)
    return fetcher_cls()

"""
Comando para popular noticias fake no portal B2C para QA/demo.

Uso:
    python manage.py seed_noticias_fake --quantidade 10

Idempotente: usa `get_or_create` por `slug`, entao rodar multiplas vezes
nao duplica. Se a quantidade pedida for maior que o pool de titulos, cicla
com sufixo para manter slugs unicos.
"""
from __future__ import annotations

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.template.defaultfilters import slugify
from django.utils import timezone

from portal.models import NoticiaPublicada


NOTICIAS_BASE = [
    {
        "titulo": "Latam lanca promocao de passagens para Europa a partir de R$ 2.590",
        "resumo": "Companhia aerea abre janela de tarifas reduzidas para voos partindo de Sao Paulo e Rio de Janeiro rumo a Madri, Lisboa, Roma e Paris.",
        "categoria": "promocoes",
        "topico": "voos internacionais",
        "tags": ["latam", "europa", "promocao"],
    },
    {
        "titulo": "GOL abre rota direta entre Brasilia e Orlando",
        "resumo": "Operacao inedita comeca no segundo semestre e encurta o tempo de viagem de brasilienses rumo aos parques tematicos da Florida.",
        "categoria": "viagens",
        "topico": "novas rotas",
        "tags": ["gol", "orlando", "rota direta"],
    },
    {
        "titulo": "Azul reduz preco de voos entre Sao Paulo e Recife em 35%",
        "resumo": "Queda de tarifa acompanha aumento de frequencias na ponte aerea SP-Recife e amplia oferta para o verao.",
        "categoria": "promocoes",
        "topico": "tarifas domesticas",
        "tags": ["azul", "recife", "tarifa"],
    },
    {
        "titulo": "Iberia relanca Avios para rotas Brasil-Madri",
        "resumo": "Programa de fidelidade da companhia espanhola volta a ofertar resgates promocionais em voos saindo de Sao Paulo, Rio e Recife.",
        "categoria": "milhas",
        "topico": "programa de fidelidade",
        "tags": ["iberia", "avios", "madri"],
    },
    {
        "titulo": "Erro de preco: Emirates com Sao Paulo-Dubai por R$ 1.800",
        "resumo": "Passagem apareceu durante a madrugada com desconto expressivo e foi rapidamente encerrada. Confira os detalhes da falha tarifaria.",
        "categoria": "promocoes",
        "topico": "erro de tarifa",
        "tags": ["emirates", "dubai", "erro de preco"],
    },
    {
        "titulo": "Smiles oferece desconto de 70% em passagens para Porto Seguro",
        "resumo": "Programa da GOL abre janela promocional de resgates para o nordeste com foco em ferias escolares.",
        "categoria": "milhas",
        "topico": "resgates",
        "tags": ["smiles", "porto seguro", "desconto"],
    },
    {
        "titulo": "Alertas de milhas: como aproveitar promocoes Sky Miles",
        "resumo": "Guia pratico para nao perder as janelas curtas de promocao do programa de fidelidade da Delta Air Lines.",
        "categoria": "milhas",
        "topico": "guia",
        "tags": ["sky miles", "delta", "guia"],
    },
    {
        "titulo": "Como funciona o programa LATAM Pass em 2025",
        "resumo": "Entenda as mudancas de categoria, bonus de pontos e parcerias do programa de fidelidade da LATAM para 2025.",
        "categoria": "milhas",
        "topico": "programa de fidelidade",
        "tags": ["latam pass", "2025", "fidelidade"],
    },
    {
        "titulo": "Guia: melhores cartoes para acumular milhas em 2025",
        "resumo": "Comparativo atualizado entre Itaucard, Nubank Ultravioleta, C6 Carbon e outros cartoes premium focados em milhas.",
        "categoria": "cartoes",
        "topico": "cartoes de credito",
        "tags": ["cartoes", "milhas", "guia 2025"],
    },
    {
        "titulo": "Azul adiciona 4 novos destinos internacionais",
        "resumo": "Companhia aerea anuncia expansao internacional com voos diretos para destinos na America Latina e Estados Unidos.",
        "categoria": "viagens",
        "topico": "novas rotas",
        "tags": ["azul", "expansao", "internacional"],
    },
]


def _build_conteudo(titulo: str, resumo: str) -> str:
    """Monta 3-5 paragrafos realistas para o corpo da noticia."""
    paragrafos = [
        f"<p>{resumo}</p>",
        (
            f"<p>A novidade foi anunciada nas ultimas horas e ja circula entre agentes "
            f"especializados em viagens aereas. Segundo apuracao da redacao NCfly, a "
            f"movimentacao faz parte de uma estrategia maior do setor para retomar "
            f"margens e atrair consumidores atentos a precos.</p>"
        ),
        (
            "<p>Passageiros interessados devem verificar disponibilidade diretamente nos "
            "canais oficiais da companhia e ficar atentos as regras de bagagem, cancelamento "
            "e reembolso antes de fechar a compra.</p>"
        ),
        (
            "<p>Programas de fidelidade e cartoes de credito com acumulo acelerado podem "
            "potencializar a economia em compras desse tipo. Recomendamos simular a compra "
            "em mais de um canal para confirmar o melhor custo-beneficio.</p>"
        ),
        (
            f"<p><strong>Dica NCfly:</strong> configure alertas personalizados para a rota "
            f"desejada e acompanhe em tempo real oscilacoes ligadas a {titulo.lower()}.</p>"
        ),
    ]
    return "\n".join(paragrafos)


class Command(BaseCommand):
    help = "Cria noticias fake publicadas para QA/demo do portal B2C."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quantidade",
            type=int,
            default=10,
            help="Quantidade de noticias a criar (padrao: 10).",
        )

    def handle(self, *args, **options):
        quantidade = max(1, int(options["quantidade"]))
        self.stdout.write(
            f"Criando ate {quantidade} noticia(s) fake (idempotente por slug)..."
        )

        agora = timezone.now()
        criadas = 0
        puladas = 0

        for i in range(quantidade):
            base = NOTICIAS_BASE[i % len(NOTICIAS_BASE)]
            # Evita colisao de slug quando quantidade > len(NOTICIAS_BASE)
            if i >= len(NOTICIAS_BASE):
                titulo = f"{base['titulo']} (edicao {i + 1})"
            else:
                titulo = base["titulo"]

            slug = slugify(titulo)[:220]
            dias_atras = random.randint(0, 14)
            horas_atras = random.randint(0, 23)
            publicada_em = agora - timedelta(days=dias_atras, hours=horas_atras)

            # URLs estaveis: nome fantasia fake + slug; `url_fonte` e obrigatorio
            url_fonte = f"https://noticias-fake.ncfly.local/{slug}"
            imagem_url = f"https://picsum.photos/seed/{slug}/1200/630"

            defaults = {
                "titulo": titulo,
                "resumo": base["resumo"],
                "conteudo": _build_conteudo(titulo, base["resumo"]),
                "categoria": base["categoria"],
                "topico": base["topico"],
                "tags_json": base["tags"],
                "imagem_url": imagem_url,
                "imagem_ilustrativa": True,
                "url_fonte": url_fonte,
                "status": "published",
                "confianca": 0.95,
                "publicada_em": publicada_em,
            }

            _, created = NoticiaPublicada.objects.get_or_create(
                slug=slug, defaults=defaults
            )
            if created:
                criadas += 1
                self.stdout.write(self.style.SUCCESS(f"  [criada] {titulo}"))
            else:
                puladas += 1
                self.stdout.write(f"  [existia] {titulo}")

        self.stdout.write(
            self.style.SUCCESS(
                f"OK - {criadas} noticia(s) criada(s), {puladas} ja existia(m)."
            )
        )

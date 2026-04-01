from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Fonte, MateriaBruta, NoticiaPublicada
from .services.ai_pipeline import NewsDraft, _apply_quality_rules, _normalize_confidence
from .services.deduplication import append_source_reference, build_story_fingerprint, find_duplicate_news
from .services.fetchers.base import extract_article_text, extract_relevant_outbound_links
from .services.fetchers.html import HtmlFetcher


class PortalRoutesTest(TestCase):
    def setUp(self):
        self.fonte = Fonte.objects.create(
            nome="Fonte Teste",
            url="https://example.com",
            tipo_coleta="html",
        )
        self.materia = MateriaBruta.objects.create(
            fonte=self.fonte,
            url_original="https://example.com/noticia",
            titulo_extraido="Notícia teste",
            texto_base="Texto base suficientemente longo para a notícia teste.",
            hash_conteudo="abc123",
        )
        self.noticia = NoticiaPublicada.objects.create(
            materia_bruta=self.materia,
            fonte=self.fonte,
            titulo="Notícia teste publicada",
            resumo="Resumo teste",
            conteudo="Conteúdo teste",
            slug="noticia-teste-publicada",
            categoria="Milhas",
            topico="Transferências Bonificadas",
            tags_json=["Milhas e Pontos", "Transferencia", "Bonus"],
            url_fonte="https://example.com/noticia",
            status="published",
            publicada_em=timezone.now(),
        )

    def test_home_publica_carrega(self):
        response = self.client.get(reverse("portal_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NC Fly")
        self.assertContains(response, self.noticia.titulo)
        self.assertContains(response, self.noticia.topico)

    def test_detalhe_noticia_carrega(self):
        response = self.client.get(reverse("portal_noticia_detalhe", kwargs={"slug": self.noticia.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.noticia.titulo)
        self.assertContains(response, self.noticia.topico)

    def test_categoria_carrega(self):
        response = self.client.get(reverse("portal_categoria", kwargs={"categoria_slug": "milhas-e-pontos"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Milhas e Pontos")
        self.assertContains(response, self.noticia.titulo)
        self.assertContains(response, "Transferências Bonificadas")
        self.assertNotContains(response, "Carregar mais notícias")

    def test_categoria_filtra_por_topico(self):
        response = self.client.get(
            reverse("portal_categoria", kwargs={"categoria_slug": "milhas-e-pontos"}),
            {"topico": "transferencias-bonificadas"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exibindo notícias do tema")
        self.assertContains(response, self.noticia.titulo)

    def test_categoria_so_mostra_carregar_mais_quando_existem_ocultas(self):
        for index in range(8):
            materia = MateriaBruta.objects.create(
                fonte=self.fonte,
                url_original=f"https://example.com/noticia-{index}",
                titulo_extraido=f"Noticia extra {index}",
                texto_base="Texto base suficientemente longo para a noticia teste.",
                hash_conteudo=f"hash-extra-{index}",
            )
            NoticiaPublicada.objects.create(
                materia_bruta=materia,
                fonte=self.fonte,
                titulo=f"Noticia extra {index}",
                resumo="Resumo teste",
                conteudo="Conteudo teste",
                slug=f"noticia-extra-{index}",
                categoria="Milhas e Pontos",
                topico="Transferências Bonificadas",
                tags_json=["Milhas e Pontos"],
                url_fonte=f"https://example.com/noticia-{index}",
                status="published",
                publicada_em=timezone.now(),
            )

        response = self.client.get(reverse("portal_categoria", kwargs={"categoria_slug": "milhas-e-pontos"}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Carregar mais notícias")
        self.assertContains(response, 'data-load-more-button')
        self.assertEqual(len(response.context["hidden_cards"]), 1)

    def test_rotas_publicas_e_painel(self):
        self.assertEqual(reverse("portal_home"), "/home/")
        self.assertEqual(reverse("portal_categoria", kwargs={"categoria_slug": "milhas-e-pontos"}), "/home/categorias/milhas-e-pontos/")
        self.assertEqual(reverse("login_custom"), "/login/")
        self.assertEqual(reverse("painel_dashboard"), "/painel/")

    def test_raiz_redireciona_para_home(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/home/")


class PortalContentQualityTest(TestCase):
    def test_extract_article_text_remove_ruido_de_navegacao(self):
        html = """
        <html>
            <body>
                <nav>Filtrar por Promocoes Ver Todos Clube de pontos</nav>
                <article>
                    <p>A LATAM liberou uma nova campanha de transferencia bonificada para clientes selecionados.</p>
                    <p>O bonus pode chegar a 30% e vale para transferencias feitas ate o fim da semana.</p>
                    <p>Deixe um comentario</p>
                </article>
            </body>
        </html>
        """
        text = extract_article_text(html)
        self.assertIn("A LATAM liberou uma nova campanha", text)
        self.assertIn("O bonus pode chegar a 30%", text)
        self.assertNotIn("Filtrar por Promocoes", text)
        self.assertNotIn("Deixe um comentario", text)

    def test_apply_quality_rules_normaliza_categoria_topico_e_tags(self):
        draft = NewsDraft(
            titulo="Promocao",
            resumo="Resumo curto",
            conteudo="Filtrar por Promocoes Ver Todos publicidade",
            categoria="promocoes",
            topico="bonus",
            tags=["bonus", "transferencia"],
            cta_url="",
            cta_label="",
            slug="promocao",
            confianca=Decimal("0.95"),
        )
        result = _apply_quality_rules(
            draft,
            {
                "titulo_extraido": "Promocao de transferencia",
                "resumo_base": "Transferencia bonificada entre programas com prazo limitado para clientes elegiveis.",
                "texto_base": "Transferencia bonificada entre programas com prazo limitado para clientes elegiveis. Ha detalhes de bonus, validade e regras para aproveitar melhor a oferta.",
                "categoria_padrao": "Promoções",
            },
        )
        self.assertEqual(result.categoria, "Promoções")
        self.assertEqual(result.topico, "Transferências e Bônus")
        self.assertIn("Transferências e Bônus", result.tags)
        self.assertLessEqual(result.confianca, Decimal("0.55"))
        self.assertIn("quality_flags", result.metadata)

    def test_apply_quality_rules_aproveita_link_externo_relevante(self):
        draft = NewsDraft(
            titulo="Oferta de hotel",
            resumo="Resumo valido com contexto suficiente para a materia.",
            conteudo="Conteudo longo o suficiente para manter a materia coerente e sem ruido editorial.",
            categoria="hoteis",
            topico="",
            tags=[],
            cta_url="",
            cta_label="",
            slug="oferta-hotel",
            confianca=Decimal("0.88"),
        )
        result = _apply_quality_rules(
            draft,
            {
                "titulo_extraido": "Oferta de hotel",
                "resumo_base": "Oferta com desconto em hospedagem.",
                "texto_base": "Oferta com desconto em hospedagem e detalhes completos para reserva.",
                "categoria_padrao": "Hotéis e Resorts",
                "outbound_links": [
                    {"url": "https://promo.exemplo.com/oferta", "label": "Aproveitar oferta agora"},
                ],
            },
        )
        self.assertEqual(result.metadata["offer_cta"]["url"], "https://promo.exemplo.com/oferta")
        self.assertEqual(result.metadata["offer_cta"]["label"], "Aproveitar oferta agora")

    def test_normalize_confidence_converte_escala_de_zero_a_dez(self):
        self.assertEqual(_normalize_confidence(Decimal("9.0")), Decimal("0.90"))
        self.assertEqual(_normalize_confidence(Decimal("1.50")), Decimal("0.15"))
        self.assertEqual(_normalize_confidence(Decimal("0.82")), Decimal("0.82"))

    def test_extract_relevant_outbound_links_filtra_sociais(self):
        html = """
        <a href="https://facebook.com/compartilhar">Facebook</a>
        <a href="https://promo.exemplo.com/oferta">Aproveitar oferta agora</a>
        """
        links = extract_relevant_outbound_links(html, "https://origem.com/materia")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["url"], "https://promo.exemplo.com/oferta")


class PortalCrawlerTest(TestCase):
    @patch("portal.services.fetchers.html.fetch_url")
    def test_html_fetcher_varre_home_categoria_paginacao_e_sitemap(self, mock_fetch_url):
        source = SimpleNamespace(
            url="https://fonte-teste.com/",
            headers_json={},
        )
        pages = {
            "https://fonte-teste.com/robots.txt": "Sitemap: https://fonte-teste.com/sitemap.xml",
            "https://fonte-teste.com/sitemap.xml": """
                <urlset>
                    <url><loc>https://fonte-teste.com/categoria/milhas/</loc></url>
                    <url><loc>https://fonte-teste.com/2026/03/noticia-via-sitemap</loc></url>
                </urlset>
            """,
            "https://fonte-teste.com/sitemap_index.xml": "",
            "https://fonte-teste.com/": """
                <a href="/categoria/milhas/">Categoria Milhas e Pontos</a>
                <a href="/2026/03/noticia-home-principal">Grande noticia de milhas e promoções para viajar melhor</a>
            """,
            "https://fonte-teste.com/categoria/milhas/": """
                <a href="/page/2/">Pagina 2 categoria milhas</a>
                <a href="/2026/03/noticia-categoria-bonus">Noticia de bonus em transferencia para clientes do programa</a>
            """,
            "https://fonte-teste.com/page/2/": """
                <a href="/2026/03/noticia-paginacao-resgate">Nova oportunidade de resgate com milhas e pontos</a>
            """,
        }

        def fake_fetch(url, headers=None, timeout=20):
            return pages.get(url, "")

        mock_fetch_url.side_effect = fake_fetch

        entries = HtmlFetcher().list_entries(source)
        urls = {entry.url for entry in entries}

        self.assertIn("https://fonte-teste.com/2026/03/noticia-home-principal", urls)
        self.assertIn("https://fonte-teste.com/2026/03/noticia-categoria-bonus", urls)
        self.assertIn("https://fonte-teste.com/2026/03/noticia-paginacao-resgate", urls)
        self.assertIn("https://fonte-teste.com/2026/03/noticia-via-sitemap", urls)


class PortalDeduplicationTest(TestCase):
    def setUp(self):
        fonte = Fonte.objects.create(nome="Fonte A", url="https://a.com", tipo_coleta="html")
        materia = MateriaBruta.objects.create(
            fonte=fonte,
            url_original="https://a.com/noticia",
            titulo_extraido="Promocao de transferencia com bonus de 30 por cento no programa",
            texto_base="Texto base grande o suficiente para manter o contexto da notícia e simular uma publicação real do portal.",
            hash_conteudo="hash-a",
        )
        metadata = {
            "story_fingerprint": build_story_fingerprint(
                "Promocao de transferencia com bonus de 30 por cento no programa",
                "Clientes elegiveis podem receber bonus adicional nesta campanha.",
                "Promoções",
                "Transferências e Bônus",
            )
        }
        self.noticia = NoticiaPublicada.objects.create(
            materia_bruta=materia,
            fonte=fonte,
            titulo="Promocao de transferencia com bonus de 30 por cento no programa",
            resumo="Clientes elegiveis podem receber bonus adicional nesta campanha.",
            conteudo="Conteudo longo simulando a materia original publicada pelo portal.",
            slug="promocao-transferencia-bonus-30",
            categoria="Promoções",
            topico="Transferências e Bônus",
            tags_json=["Promoções", "Transferências e Bônus", "Bônus"],
            url_fonte="https://a.com/noticia",
            status="published",
            metadata_json=metadata,
        )

    def test_find_duplicate_news_detecta_mesma_noticia_em_outra_fonte(self):
        duplicate = find_duplicate_news(
            "Transferencia bonificada oferece bonus de 30 por cento para clientes do programa",
            "Campanha promocional garante bonus adicional para clientes elegiveis na transferencia.",
            "Promoções",
            "Transferências e Bônus",
        )
        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate.pk, self.noticia.pk)

    def test_append_source_reference_nao_duplica_mesma_url(self):
        metadata = append_source_reference({}, source_name="Fonte A", article_url="https://a.com/noticia", title="Titulo")
        metadata = append_source_reference(metadata, source_name="Fonte A", article_url="https://a.com/noticia", title="Titulo")
        self.assertEqual(len(metadata["source_references"]), 1)

import json
import os
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import quote
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from gestao.models import AlertaViagem
from .models import Fonte, LeadPlataforma, MateriaBruta, NoticiaPublicada, PortalMetricDaily
from .services.ai_pipeline import (
    NewsDraft,
    _apply_quality_rules,
    _build_cover_prompt,
    _normalize_confidence,
    ensure_cover_for_news,
)
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
        self.alerta = AlertaViagem.objects.create(
            titulo="GRU para MIA com milhas",
            conteudo="Alerta de oportunidade para emissao no programa informado.",
            continente="AmÃ©rica do Norte",
            pais="Estados Unidos",
            cidade_destino="Miami",
            origem="GRU",
            destino="MIA",
            classe=AlertaViagem.CLASSE_ECONOMICA,
            programa_fidelidade="Smiles",
            companhia_aerea="American Airlines",
            valor_milhas=70000,
            datas_ida=["2026-05-01", "2026-05-03"],
            datas_volta=["2026-05-07", "2026-05-09"],
            ativo=True,
        )
        self.alerta_relacionado = AlertaViagem.objects.create(
            titulo="GIG para JFK com milhas",
            conteudo="Outra oportunidade valida para a vitrine publica.",
            continente="AmÃ©rica do Norte",
            pais="Estados Unidos",
            cidade_destino="Nova York",
            origem="GIG",
            destino="JFK",
            classe=AlertaViagem.CLASSE_EXECUTIVA,
            programa_fidelidade="Smiles",
            companhia_aerea="United Airlines",
            valor_milhas=78000,
            datas_ida=["2026-05-10"],
            ativo=True,
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
        self.assertContains(response, "Receba as melhores ofertas de milhas")
        self.assertContains(response, "GRU")
        self.assertContains(response, "MIA")
        self.assertContains(response, "A partir de")
        self.assertContains(response, "70.000 milhas")
        self.assertNotContains(response, ">Login<", html=False)

    def test_home_limita_carrossel_de_alertas_a_quinze_cards(self):
        for index in range(20):
            AlertaViagem.objects.create(
                titulo=f"Alerta extra {index}",
                conteudo="Alerta adicional para validar o limite do carrossel.",
                continente="AmÃƒÂ©rica do Norte",
                pais="Estados Unidos",
                cidade_destino=f"Destino {index}",
                origem="GRU",
                destino=f"M{index:02d}"[:3],
                classe=AlertaViagem.CLASSE_ECONOMICA,
                programa_fidelidade="Smiles",
                companhia_aerea="American Airlines",
                valor_milhas=60000 + index,
                datas_ida=["2026-05-01"],
                ativo=True,
            )

        response = self.client.get(reverse("portal_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ver mais")
        self.assertEqual(response.content.decode().count("data-alerts-slide"), 15)

    def test_home_publica_filtra_por_busca(self):
        outra_materia = MateriaBruta.objects.create(
            fonte=self.fonte,
            url_original="https://example.com/cartao-black",
            titulo_extraido="Cartao black",
            texto_base="Texto sobre cartoes premium e beneficios exclusivos.",
            hash_conteudo="busca456",
        )
        NoticiaPublicada.objects.create(
            materia_bruta=outra_materia,
            fonte=self.fonte,
            titulo="Cartao black com novos beneficios",
            resumo="Resumo sobre cartoes premium.",
            conteudo="Conteudo sobre cartoes de credito e acesso a salas VIP.",
            slug="cartao-black-beneficios",
            categoria="Cartoes de Credito",
            topico="Cartoes Premium",
            tags_json=["Cartoes de Credito"],
            url_fonte="https://example.com/cartao-black",
            status="published",
            publicada_em=timezone.now(),
        )

        response = self.client.get(reverse("portal_home"), {"q": "transferencias"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resultados para")
        self.assertContains(response, self.noticia.titulo)
        self.assertNotContains(response, "Cartao black com novos beneficios")

    def test_home_publica_exibe_estado_sem_resultado_na_busca(self):
        response = self.client.get(reverse("portal_home"), {"q": "destino-inexistente"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resultados para")
        self.assertContains(response, "Não encontramos notícias para essa busca.")
        self.assertContains(response, "Limpar busca")

    def test_detalhe_noticia_carrega(self):
        response = self.client.get(self.noticia.get_absolute_url())
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
        self.assertEqual(reverse("portal_alertas"), "/home/alertas/")
        self.assertEqual(reverse("portal_alerta_detalhe", args=[self.alerta.id]), f"/home/alertas/{self.alerta.id}/")
        self.assertEqual(reverse("portal_plataforma_saas"), "/home/plataforma/")
        self.assertEqual(reverse("portal_plataforma_contato"), "/home/plataforma/contato/")
        self.assertEqual(reverse("portal_sobre"), "/home/sobre-nos/")
        self.assertEqual(reverse("portal_privacidade"), "/home/politica-de-privacidade/")
        self.assertEqual(reverse("portal_termos"), "/home/termos-de-uso/")
        self.assertEqual(reverse("portal_privacidade_plataforma"), "/plataforma/privacidade/")
        self.assertEqual(reverse("portal_termos_plataforma"), "/plataforma/termos-de-uso/")
        self.assertEqual(reverse("portal_dpa_plataforma"), "/plataforma/dpa/")
        self.assertEqual(reverse("portal_seguranca_plataforma"), "/plataforma/seguranca/")
        self.assertEqual(reverse("portal_aceite_plataforma"), "/plataforma/aceite/")
        self.assertEqual(reverse("portal_categoria", kwargs={"categoria_slug": "milhas-e-pontos"}), "/home/categorias/milhas-e-pontos/")
        self.assertEqual(reverse("portal_noticia_detalhe", kwargs={"categoria_slug": "milhas-e-pontos", "slug": "teste"}), "/home/categorias/milhas-e-pontos/teste/")
        self.assertEqual(reverse("portal_noticia_redirect", kwargs={"slug": "teste"}), "/home/noticias/teste/")
        self.assertEqual(self.noticia.get_absolute_url(), "/home/categorias/milhas-e-pontos/noticia-teste-publicada/")
        self.assertEqual(reverse("login_custom"), "/login/")
        self.assertEqual(reverse("painel_dashboard"), "/painel/")

    def test_listagem_publica_de_alertas_limita_carga_inicial_a_seis(self):
        for index in range(7):
            AlertaViagem.objects.create(
                titulo=f"Alerta publico {index}",
                conteudo="Carga adicional para validar o botao carregar mais.",
                continente="AmÃƒÂ©rica do Norte",
                pais="Estados Unidos",
                cidade_destino=f"Destino publico {index}",
                origem="GRU",
                destino=f"X{index:02d}"[:3],
                classe=AlertaViagem.CLASSE_ECONOMICA,
                programa_fidelidade="Smiles",
                companhia_aerea="American Airlines",
                valor_milhas=65000 + index,
                datas_ida=["2026-05-11"],
                ativo=True,
            )

        response = self.client.get(reverse("portal_alertas"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Carregar mais alertas")
        self.assertContains(response, 'data-load-more-button')
        self.assertEqual(response.context["alerts_page_size"], 6)
        self.assertEqual(response.context["hidden_alert_count"], 3)

    def test_listagem_publica_de_alertas_filtra_por_aeroporto_programa_e_companhia(self):
        response = self.client.get(
            reverse("portal_alertas"),
            {"aeroporto": "GRU", "programa": "Smiles", "companhia": "American Airlines"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["alertas_publicos"]), 1)
        self.assertEqual(response.context["selected_alert_filters"]["aeroporto"], "GRU")
        self.assertEqual(response.context["selected_alert_filters"]["programa"], "Smiles")
        self.assertEqual(response.context["selected_alert_filters"]["companhia"], "American Airlines")
        self.assertContains(response, "American Airlines")
        self.assertContains(response, "Smiles")

    def test_raiz_redireciona_para_home(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/home/")

    def test_paginas_institucionais_carregam(self):
        for route_name in (
            "portal_alertas",
            "portal_plataforma_saas",
            "portal_plataforma_contato",
            "portal_sobre",
            "portal_privacidade",
            "portal_termos",
            "portal_privacidade_plataforma",
            "portal_termos_plataforma",
            "portal_dpa_plataforma",
            "portal_seguranca_plataforma",
        ):
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "NC Fly News")

    def test_plataforma_saas_captura_lead_rapido(self):
        response = self.client.post(
            reverse("portal_plataforma_saas"),
            {
                "nome": "Maria Oliveira",
                "email": "maria@example.com",
                "telefone": "(11) 99999-0000",
                "aceite_contato": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeadPlataforma.objects.count(), 1)
        lead = LeadPlataforma.objects.get()
        self.assertEqual(lead.nome_completo, "Maria Oliveira")
        self.assertEqual(lead.email, "maria@example.com")
        self.assertEqual(lead.telefone, "(11) 99999-0000")
        self.assertEqual(lead.empresa, "")
        self.assertContains(response, "Recebemos seu interesse")

    def test_detalhe_alerta_publico_carrega_com_cta_do_programa(self):
        with patch("portal.services.public_alerts._build_ai_public_copy", return_value={}):
            response = self.client.get(reverse("portal_alerta_detalhe", args=[self.alerta.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resgatar agora")
        self.assertContains(response, "https://www.smiles.com.br")
        self.assertContains(response, "Sobre esta oferta")
        self.assertContains(response, "Datas dispon")
        self.assertContains(response, "Alertas semelhantes")
        self.assertContains(response, "A partir de")
        self.assertContains(response, "70.000 milhas")

    def test_alerta_expirado_nao_aparece_no_detalhe_publico(self):
        alerta_antigo = AlertaViagem.objects.create(
            titulo="SSA para MAD expirado",
            conteudo="Alerta expirado.",
            continente="Europa",
            pais="Espanha",
            cidade_destino="Madri",
            origem="SSA",
            destino="MAD",
            classe=AlertaViagem.CLASSE_EXECUTIVA,
            programa_fidelidade="Latam Pass",
            companhia_aerea="Iberia",
            valor_milhas=82000,
            datas_ida=[],
            datas_volta=[],
            ativo=True,
        )
        AlertaViagem.objects.filter(pk=alerta_antigo.pk).update(
            criado_em=timezone.now() - timedelta(days=8)
        )

        response = self.client.get(reverse("portal_alerta_detalhe", args=[alerta_antigo.id]))
        self.assertEqual(response.status_code, 404)

    def test_home_footer_publico_nao_exibe_links_juridicos_da_plataforma(self):
        response = self.client.get(reverse("portal_home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Termos da Plataforma")
        self.assertNotContains(response, "Privacidade da Plataforma")

    def test_pagina_saas_exibe_footer_proprio_sem_links_juridicos_da_plataforma(self):
        response = self.client.get(reverse("portal_plataforma_saas"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plataforma NC Fly")
        self.assertContains(response, "FAQ")
        self.assertNotContains(response, "Termos da Plataforma")
        self.assertNotContains(response, "Seguranca e Uso Aceitavel")

    def test_pagina_contato_da_plataforma_exibe_modal_de_aceite(self):
        response = self.client.get(reverse("portal_plataforma_contato"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Solicitar contato")
        self.assertContains(response, 'data-lead-modal', html=False)
        self.assertContains(response, 'data-lead-open-modal', html=False)

    def test_detalhe_usa_footer_principal(self):
        response = self.client.get(self.noticia.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pol")
        self.assertContains(response, "Termos de Uso")

    def test_home_publica_exibe_estado_sem_resultado_na_busca(self):
        response = self.client.get(reverse("portal_home"), {"q": "destino-inexistente"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resultados para")
        self.assertContains(response, "N&atilde;o encontramos not&iacute;cias para essa busca.")
        self.assertContains(response, "Limpar busca")

    def test_detalhe_usa_footer_principal(self):
        response = self.client.get(self.noticia.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quem Somos")
        self.assertContains(response, "Pol&iacute;tica de Privacidade")

class PortalSeoTest(TestCase):
    def setUp(self):
        self.fonte = Fonte.objects.create(
            nome="Fonte SEO",
            url="https://example.com",
            tipo_coleta="html",
        )
        self.materia = MateriaBruta.objects.create(
            fonte=self.fonte,
            url_original="https://example.com/noticia-seo",
            titulo_extraido="Noticia SEO",
            texto_base="Texto base suficientemente longo para a notícia de SEO.",
            hash_conteudo="seo123",
        )
        self.noticia = NoticiaPublicada.objects.create(
            materia_bruta=self.materia,
            fonte=self.fonte,
            titulo="Notícia SEO publicada",
            resumo="Resumo SEO para testar meta description e canonical.",
            conteudo="Conteúdo SEO longo o suficiente para estruturar a página pública com article schema.",
            slug="noticia-seo-publicada",
            categoria="Milhas e Pontos",
            topico="Transferências Bonificadas",
            tags_json=["Milhas e Pontos", "Transferências Bonificadas"],
            url_fonte="https://example.com/noticia-seo",
            status="published",
            publicada_em=timezone.now(),
        )
        self.alerta = AlertaViagem.objects.create(
            titulo="BSB para LHR com milhas",
            conteudo="Alerta SEO para sitemap publico.",
            continente="Europa",
            pais="Reino Unido",
            cidade_destino="Londres",
            origem="BSB",
            destino="LHR",
            classe=AlertaViagem.CLASSE_EXECUTIVA,
            programa_fidelidade="Smiles",
            companhia_aerea="British Airways",
            valor_milhas=90000,
            datas_ida=["2026-04-25"],
            ativo=True,
        )

    def test_home_publica_renderiza_tags_basicas_de_seo(self):
        response = self.client.get(reverse("portal_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<meta name="description"', html=False)
        self.assertContains(response, '<link rel="canonical" href="http://testserver/home/">', html=False)
        self.assertContains(response, 'property="og:title"', html=False)

    def test_detalhe_renderiza_schema_e_canonical(self):
        response = self.client.get(self.noticia.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "application/ld+json")
        self.assertContains(response, "NewsArticle")
        self.assertContains(
            response,
            f'<link rel="canonical" href="http://testserver{self.noticia.get_absolute_url()}">',
            html=False,
        )

    def test_robots_txt_expoe_sitemap(self):
        response = self.client.get(reverse("portal_robots"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User-agent: *")
        self.assertContains(response, "Sitemap: http://testserver/sitemap.xml")

    def test_sitemap_xml_expoe_urls_publicas(self):
        response = self.client.get(reverse("portal_sitemap"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/home/")
        self.assertContains(response, "/home/alertas/")
        self.assertContains(response, f"/home/alertas/{self.alerta.id}/")
        self.assertContains(response, "/home/plataforma/")
        self.assertNotContains(response, "/home/plataforma/contato/")
        self.assertContains(response, "/home/categorias/milhas-e-pontos/")
        self.assertContains(response, self.noticia.get_absolute_url())


@override_settings(
    GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST123456",
    GOOGLE_SEARCH_CONSOLE_VERIFICATION="google-site-verification-token",
)
class PortalAnalyticsTest(TestCase):
    def setUp(self):
        self.fonte = Fonte.objects.create(
            nome="Fonte Analytics",
            url="https://example.com",
            tipo_coleta="html",
        )
        self.materia = MateriaBruta.objects.create(
            fonte=self.fonte,
            url_original="https://example.com/noticia-analytics",
            titulo_extraido="Noticia analytics",
            texto_base="Texto base suficientemente longo para a noticia analytics.",
            hash_conteudo="analytics123",
        )
        self.noticia = NoticiaPublicada.objects.create(
            materia_bruta=self.materia,
            fonte=self.fonte,
            titulo="Noticia analytics publicada",
            resumo="Resumo analytics para testar Search Console e GA4.",
            conteudo="Conteudo analytics longo o suficiente para testar a instrumentacao publica.",
            slug="noticia-analytics-publicada",
            categoria="Promoções",
            topico="Transferências e Bônus",
            tags_json=["Promoções", "Transferências e Bônus"],
            url_fonte="https://example.com/noticia-analytics",
            status="published",
            metadata_json={
                "offer_cta": {
                    "url": "https://promo.exemplo.com/oferta",
                    "label": "Aproveitar oferta",
                }
            },
            publicada_em=timezone.now(),
        )

    def test_home_renderiza_verificacao_do_search_console_e_script_do_ga4(self):
        self.client.cookies["ncfly_cookie_preferences"] = quote(
            json.dumps({"version": "2026-04", "essential": True, "analytics": True})
        )
        response = self.client.get(reverse("portal_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="google-site-verification"', html=False)
        self.assertContains(response, "google-site-verification-token")
        self.assertContains(response, "https://www.googletagmanager.com/gtag/js?id=G-TEST123456")
        self.assertContains(response, 'gtag("config", "G-TEST123456")')

    def test_detalhe_renderiza_marcacoes_de_analytics(self):
        response = self.client.get(self.noticia.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-analytics-view="article"', html=False)
        self.assertContains(response, 'data-analytics-event="click_offer_link"', html=False)

    def test_home_sem_consentimento_nao_renderiza_script_do_ga4(self):
        response = self.client.get(reverse("portal_home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "https://www.googletagmanager.com/gtag/js?id=G-TEST123456")


class PortalCookieAndAiDiscoveryTest(TestCase):
    def test_home_renderiza_banner_de_cookies_por_padrao(self):
        response = self.client.get(reverse("portal_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Privacidade e cookies")
        self.assertContains(response, "data-cookie-action=\"accept\"", html=False)
        self.assertContains(response, "Prefer")
        self.assertContains(response, 'data-cookie-setting="analytics" checked', html=False)

    def test_llms_txt_expoe_contexto_editorial(self):
        response = self.client.get(reverse("portal_llms"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "# NC Fly News")
        self.assertContains(response, "Milhas e Pontos")
        self.assertContains(response, "Plataforma NC Fly")

    def test_home_registra_page_view_first_party(self):
        response = self.client.get(reverse("portal_home"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PortalMetricDaily.objects.filter(
                metric_type="page_view",
                path="/home/",
                section="home",
                site_environment="local",
                site_host="testserver",
            ).exists()
        )

    def test_endpoint_registra_click_first_party(self):
        response = self.client.post(
            reverse("portal_metrics_event"),
            data=json.dumps(
                {
                    "event_name": "click_categoria",
                    "path": "/home/",
                    "section": "home_categories",
                    "article_slug": "",
                    "article_category": "Milhas e Pontos",
                    "article_topic": "",
                }
            ),
            content_type="application/json",
            HTTP_ORIGIN="http://testserver",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PortalMetricDaily.objects.filter(
                metric_type="click",
                event_name="click_categoria",
                path="/home/",
                section="home_categories",
                site_environment="local",
                site_host="testserver",
            ).exists()
        )

    def test_endpoint_aceita_evento_da_landing_saas(self):
        response = self.client.post(
            reverse("portal_metrics_event"),
            data=json.dumps(
                {
                    "event_name": "click_cta_saas",
                    "path": "/home/plataforma/",
                    "section": "saas_hero",
                    "article_slug": "",
                    "article_category": "",
                    "article_topic": "",
                }
            ),
            content_type="application/json",
            HTTP_ORIGIN="http://testserver",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PortalMetricDaily.objects.filter(
                metric_type="click",
                event_name="click_cta_saas",
                path="/home/plataforma/",
                section="saas_hero",
            ).exists()
        )


class PortalLeadContactTest(TestCase):
    def test_post_valido_cria_lead(self):
        response = self.client.post(
            reverse("portal_plataforma_contato"),
            data={
                "nome_completo": "Maria Oliveira",
                "empresa": "Operadora Teste",
                "cargo": "Diretora",
                "email": "maria@example.com",
                "telefone": "(11) 99999-0000",
                "equipe_tamanho": "3-5",
                "mensagem": "Quero entender como organizar cotacoes e alertas.",
                "lead_terms_accept": "1",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeadPlataforma.objects.count(), 1)
        lead = LeadPlataforma.objects.get()
        self.assertEqual(lead.nome_completo, "Maria Oliveira")
        self.assertEqual(lead.status, "novo")
        self.assertEqual(lead.aceite_versao, "2026-04-lead")
        self.assertEqual(lead.source_environment, "local")
        self.assertEqual(lead.source_host, "testserver")
        self.assertContains(response, "Recebemos seu contato")

    def test_post_sem_aceite_nao_cria_lead(self):
        response = self.client.post(
            reverse("portal_plataforma_contato"),
            data={
                "nome_completo": "Maria Oliveira",
                "empresa": "Operadora Teste",
                "email": "maria@example.com",
                "telefone": "(11) 99999-0000",
                "lead_terms_accept": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeadPlataforma.objects.count(), 0)
        self.assertContains(response, "Abra o termo de aceite")


class PortalArticleSeoMetadataTest(TestCase):
    def setUp(self):
        self.fonte = Fonte.objects.create(
            nome="Fonte Meta SEO",
            url="https://example.com",
            tipo_coleta="html",
        )
        self.materia = MateriaBruta.objects.create(
            fonte=self.fonte,
            url_original="https://example.com/noticia-meta",
            titulo_extraido="Noticia meta",
            texto_base="Texto base suficientemente longo para a noticia.",
            hash_conteudo="meta123",
        )
        self.noticia = NoticiaPublicada.objects.create(
            materia_bruta=self.materia,
            fonte=self.fonte,
            titulo="Titulo editorial interno",
            resumo="Resumo editorial interno",
            conteudo="Conteudo editorial interno longo o suficiente para gerar schema e metadados na pagina.",
            slug="titulo-editorial-interno",
            categoria="Milhas e Pontos",
            topico="Transferencias Bonificadas",
            tags_json=["Milhas e Pontos", "Transferencias Bonificadas", "LATAM Pass"],
            url_fonte="https://example.com/noticia-meta",
            status="published",
            metadata_json={
                "seo": {
                    "title": "Titulo SEO para Google",
                    "meta_description": "Meta description otimizada para busca com foco claro no assunto principal da noticia.",
                }
            },
            publicada_em=timezone.now(),
        )

    def test_detalhe_prioriza_metadados_seo_salvos(self):
        response = self.client.get(self.noticia.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<title>Titulo SEO para Google | NC Fly News</title>", html=False)
        self.assertContains(response, 'content="Meta description otimizada para busca com foco claro no assunto principal da notícia."', html=False)


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

    def test_cover_prompt_reforca_originalidade_visual(self):
        prompt = _build_cover_prompt(
            "Transferencia bonificada de 30% entre programas",
            "Campanha promocional com prazo curto e regras especificas para clientes elegiveis.",
            "Milhas e Pontos",
        )
        self.assertIn("nova variacao visual", prompt)
        self.assertIn("marcas, programas, companhias", prompt)
        self.assertIn("nao uma copia da capa vista no site de referencia", prompt)
        self.assertIn("Sem texto, sem marcas d'agua", prompt)

    @patch("portal.services.ai_pipeline._save_generated_file", return_value="portal/noticias/generated/teste.svg")
    def test_force_ai_images_sem_geracao_mantem_imagem_da_fonte(self, mock_save_generated_file):
        draft = NewsDraft(
            titulo="Oferta de hotel",
            resumo="Resumo da oferta com contexto suficiente para a capa.",
            conteudo="Conteudo editorial.",
            categoria="Hoteis e Resorts",
            topico="Promocoes de Hospedagem",
            tags=[],
            cta_url="",
            cta_label="",
            slug="oferta-de-hotel",
            confianca=Decimal("0.80"),
            imagem_url="https://origem.com/imagem.jpg",
        )

        with patch.dict(
            os.environ,
            {
                "PORTAL_GENERATE_AI_IMAGES": "0",
                "PORTAL_FORCE_AI_IMAGES": "1",
            },
            clear=False,
        ):
            storage_path, illustrative = ensure_cover_for_news(draft)

        self.assertIsNone(storage_path)
        self.assertFalse(illustrative)
        mock_save_generated_file.assert_not_called()

    @patch("portal.services.ai_pipeline._generate_ai_cover", return_value=("portal/noticias/generated/teste.png", True))
    def test_force_ai_images_usa_imagem_da_fonte_como_referencia_quando_habilitado(self, mock_generate_ai_cover):
        draft = NewsDraft(
            titulo="Oferta de hotel",
            resumo="Resumo da oferta com contexto suficiente para a capa.",
            conteudo="Conteudo editorial.",
            categoria="Hoteis e Resorts",
            topico="Promocoes de Hospedagem",
            tags=[],
            cta_url="",
            cta_label="",
            slug="oferta-de-hotel",
            confianca=Decimal("0.80"),
            imagem_url="https://origem.com/imagem.jpg",
        )

        with patch.dict(
            os.environ,
            {
                "PORTAL_GENERATE_AI_IMAGES": "1",
                "PORTAL_FORCE_AI_IMAGES": "1",
                "PORTAL_USE_SOURCE_IMAGE_REFERENCE": "1",
            },
            clear=False,
        ):
            storage_path, illustrative = ensure_cover_for_news(draft)

        self.assertEqual(storage_path, "portal/noticias/generated/teste.png")
        self.assertTrue(illustrative)
        _, kwargs = mock_generate_ai_cover.call_args
        self.assertEqual(kwargs["reference_image_url"], "https://origem.com/imagem.jpg")
        self.assertIn("Edite a imagem de referencia", mock_generate_ai_cover.call_args.args[0])

    def test_sem_force_ai_images_mantem_imagem_da_fonte(self):
        draft = NewsDraft(
            titulo="Oferta de hotel",
            resumo="Resumo da oferta com contexto suficiente para a capa.",
            conteudo="Conteudo editorial.",
            categoria="Hoteis e Resorts",
            topico="Promocoes de Hospedagem",
            tags=[],
            cta_url="",
            cta_label="",
            slug="oferta-de-hotel",
            confianca=Decimal("0.80"),
            imagem_url="https://origem.com/imagem.jpg",
        )

        with patch.dict(
            os.environ,
            {
                "PORTAL_GENERATE_AI_IMAGES": "1",
                "PORTAL_FORCE_AI_IMAGES": "0",
            },
            clear=False,
        ):
            storage_path, illustrative = ensure_cover_for_news(draft)

        self.assertIsNone(storage_path)
        self.assertFalse(illustrative)


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

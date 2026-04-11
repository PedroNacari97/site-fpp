import hashlib
import json
import os
from io import StringIO
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import quote
from unittest.mock import Mock, patch

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from gestao.models import Aeroporto, AlertaViagem
from gestao.services.alerta_upsert import create_or_update_alerta
from .models import (
    AlertEmailDigestItem,
    Fonte,
    LeadAlertaEmail,
    LeadPlataforma,
    MateriaBruta,
    NoticiaPublicada,
    PortalMetricDaily,
)
from .services.ai_pipeline import (
    NewsDraft,
    _apply_quality_rules,
    _build_cover_prompt,
    _extract_cover_brand_label,
    _normalize_confidence,
    _render_svg_cover,
    _resolve_cover_brand_theme,
    ensure_cover_for_news,
)
from .services.alert_email_broadcasts import build_alert_unsubscribe_token, send_pending_alert_digest
from .services.deduplication import append_source_reference, build_story_fingerprint, find_duplicate_news
from .services.fetchers.base import extract_article_text, extract_relevant_outbound_links
from .services.fetchers.html import HtmlFetcher
from .templatetags.portal_extras import portal_content


class PortalRoutesTest(TestCase):
    def setUp(self):
        cache.clear()
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
        self.assertContains(response, "Quer receber novos alertas direto no seu e-mail?")
        self.assertContains(response, "GRU")
        self.assertContains(response, "MIA")
        self.assertContains(response, "A partir de")
        self.assertContains(response, "70.000 milhas")
        self.assertNotContains(response, ">Login<", html=False)

    @override_settings(PORTAL_CONTACT_WHATSAPP="(11) 99999-0000")
    def test_home_publica_exibe_botao_de_whatsapp_quando_configurado(self):
        response = self.client.get(reverse("portal_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-alert-whatsapp', html=False)
        self.assertContains(response, 'data-whatsapp-number="(11) 99999-0000"', html=False)
        self.assertContains(response, "Sem milhas? Pe&ccedil;a cota&ccedil;&atilde;o.")
        self.assertContains(
            response,
            'data-whatsapp-message="Ol&aacute;! Vi o alerta GRU para MIA no portal NC Fly News e gostaria de fazer uma cota&ccedil;&atilde;o."',
            html=False,
        )
        self.assertContains(response, 'data-alert-link="', html=False)

    @override_settings(PORTAL_CONTACT_WHATSAPP="", PORTAL_CONTACT_PHONE="12991722902")
    def test_home_publica_usa_telefone_como_fallback_do_whatsapp(self):
        response = self.client.get(reverse("portal_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-alert-whatsapp', html=False)
        self.assertContains(response, 'data-whatsapp-number="12991722902"', html=False)

    @override_settings(PORTAL_CONTACT_WHATSAPP="", PORTAL_CONTACT_PHONE="")
    def test_home_publica_omite_botao_de_whatsapp_sem_configuracao(self):
        response = self.client.get(reverse("portal_home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-alert-whatsapp', html=False)

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
        self.assertEqual(response.content.decode().count("data-alerts-slide"), 15)

    def test_home_publica_usa_nome_do_aeroporto_quando_cidade_nao_esta_disponivel(self):
        Aeroporto.objects.create(
            nome="Aeroporto Internacional de Guarulhos",
            sigla="GRU",
            cidade="",
            estado="SP",
        )

        response = self.client.get(reverse("portal_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aeroporto Internacional de Guarulhos")

    def test_home_publica_mantem_alerta_visivel_ate_quinze_dias(self):
        AlertaViagem.objects.filter(id=self.alerta.id).update(criado_em=timezone.now() - timedelta(days=10))
        self.alerta.refresh_from_db()

        response = self.client.get(reverse("portal_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.alerta.origem)
        self.assertContains(response, self.alerta.destino)

    def test_detalhe_alerta_publico_aceita_alerta_ate_quinze_dias(self):
        AlertaViagem.objects.filter(id=self.alerta.id).update(criado_em=timezone.now() - timedelta(days=10))
        self.alerta.refresh_from_db()

        response = self.client.get(reverse("portal_alerta_detalhe", args=[self.alerta.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.alerta.origem)
        self.assertContains(response, self.alerta.destino)

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
        self.assertEqual(reverse("portal_termos_alertas_email"), "/home/alertas/termos-de-recebimento/")
        self.assertEqual(reverse("portal_plataforma_saas"), "/home/plataforma/")
        self.assertEqual(reverse("portal_plataforma_contato"), "/home/plataforma/contato/")
        self.assertEqual(reverse("portal_sobre"), "/home/sobre-nos/")
        self.assertEqual(reverse("portal_fale_conosco"), "/home/fale-conosco/")
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
        self.assertEqual(
            response.context["hidden_alert_count"],
            max(0, len(response.context["alertas_publicos"]) - response.context["alerts_page_size"]),
        )

    def test_listagem_publica_de_alertas_filtra_por_aeroporto_programa_companhia_e_classe(self):
        response = self.client.get(
            reverse("portal_alertas"),
            {
                "aeroporto": "GRU",
                "programa": "Smiles",
                "companhia": "American Airlines",
                "classe": AlertaViagem.CLASSE_ECONOMICA,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["alertas_publicos"]), 1)
        self.assertEqual(response.context["selected_alert_filters"]["aeroporto"], "GRU")
        self.assertEqual(response.context["selected_alert_filters"]["programa"], "Smiles")
        self.assertEqual(response.context["selected_alert_filters"]["companhia"], "American Airlines")
        self.assertEqual(response.context["selected_alert_filters"]["classe"], AlertaViagem.CLASSE_ECONOMICA)
        self.assertContains(response, "American Airlines")
        self.assertContains(response, "Smiles")
        self.assertContains(response, 'name="classe"')
        self.assertContains(response, "Econ")

    def test_listagem_publica_de_alertas_filtra_por_classe_executiva(self):
        response = self.client.get(reverse("portal_alertas"), {"classe": AlertaViagem.CLASSE_EXECUTIVA})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["alertas_publicos"]), 1)
        self.assertEqual(response.context["alertas_publicos"][0]["id"], self.alerta_relacionado.id)
        self.assertEqual(response.context["selected_alert_filters"]["classe"], AlertaViagem.CLASSE_EXECUTIVA)

    def test_listagem_publica_de_alertas_exibe_nome_completo_dos_aeroportos_nos_cards(self):
        Aeroporto.objects.create(
            nome="Aeroporto Internacional de Guarulhos",
            sigla="GRU",
            cidade="Sao Paulo",
            estado="SP",
        )
        Aeroporto.objects.create(
            nome="Miami International Airport",
            sigla="MIA",
            cidade="Miami",
            estado="FL",
        )

        response = self.client.get(reverse("portal_alertas"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aeroporto Internacional de Guarulhos - Sao Paulo")
        self.assertContains(response, "Miami International Airport - Miami")

    def test_listagem_publica_de_alertas_filtra_por_nome_completo_do_aeroporto(self):
        Aeroporto.objects.create(
            nome="Aeroporto Internacional de Guarulhos",
            sigla="GRU",
            cidade="Sao Paulo",
            estado="SP",
        )
        Aeroporto.objects.create(
            nome="Miami International Airport",
            sigla="MIA",
            cidade="Miami",
            estado="FL",
        )

        response = self.client.get(
            reverse("portal_alertas"),
            {"aeroporto": "Aeroporto Internacional de Guarulhos"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["alertas_publicos"]), 1)
        self.assertEqual(
            response.context["selected_alert_filters"]["aeroporto"],
            "Aeroporto Internacional de Guarulhos",
        )
        self.assertContains(response, "Aeroporto Internacional de Guarulhos")

    def test_listagem_publica_de_alertas_filtra_por_label_composto_do_destino(self):
        Aeroporto.objects.create(
            nome="Miami International Airport",
            sigla="MIA",
            cidade="Miami",
            estado="FL",
        )

        response = self.client.get(
            reverse("portal_alertas"),
            {"aeroporto": "Miami International Airport - Miami"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["alertas_publicos"]), 1)
        self.assertContains(response, "Miami International Airport - Miami")

    def test_listagem_publica_de_alertas_mantem_alerta_visivel_ate_quinze_dias(self):
        AlertaViagem.objects.filter(id=self.alerta.id).update(criado_em=timezone.now() - timedelta(days=10))
        self.alerta.refresh_from_db()

        response = self.client.get(reverse("portal_alertas"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.alerta.origem)
        self.assertContains(response, self.alerta.destino)

    @override_settings(PORTAL_CONTACT_WHATSAPP="(11) 99999-0000")
    def test_listagem_publica_de_alertas_exibe_botao_de_whatsapp(self):
        response = self.client.get(reverse("portal_alertas"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-alert-whatsapp', html=False)
        self.assertContains(response, "Sem milhas? Pe&ccedil;a cota&ccedil;&atilde;o.")
        self.assertContains(
            response,
            'data-whatsapp-message="Ol&aacute;! Vi o alerta GRU para MIA no portal NC Fly News e gostaria de fazer uma cota&ccedil;&atilde;o."',
            html=False,
        )

    def test_raiz_redireciona_para_home(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/home/")

    def test_paginas_institucionais_carregam(self):
        for route_name in (
            "portal_alertas",
            "portal_termos_alertas_email",
            "portal_plataforma_saas",
            "portal_plataforma_contato",
            "portal_sobre",
            "portal_fale_conosco",
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

    @override_settings(PORTAL_CONTACT_PHONE="12991722902")
    def test_fale_conosco_exibe_telefone_institucional_quando_configurado(self):
        response = self.client.get(reverse("portal_fale_conosco"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "(12) 99172-2902")
        self.assertContains(response, 'href="tel:12991722902"', html=False)

    @override_settings(
        PORTAL_CONTACT_EMAIL="atendimento@ncfly.com.br",
        PORTAL_PARTNERSHIP_EMAIL="parceria@ncfly.com.br",
    )
    def test_fale_conosco_exibe_emails_institucionais_quando_configurados(self):
        response = self.client.get(reverse("portal_fale_conosco"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "atendimento@ncfly.com.br")
        self.assertContains(response, "parceria@ncfly.com.br")
        self.assertContains(response, 'href="mailto:atendimento@ncfly.com.br"', html=False)
        self.assertContains(response, 'href="mailto:parceria@ncfly.com.br"', html=False)

    @override_settings(PORTAL_CONTACT_PHONE="12991722902")
    def test_home_footer_exibe_telefone_institucional_quando_configurado(self):
        response = self.client.get(reverse("portal_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Telefone: (12) 99172-2902")
        self.assertContains(response, 'href="tel:12991722902"', html=False)

    @override_settings(PORTAL_CONTACT_EMAIL="atendimento@ncfly.com.br")
    def test_home_footer_exibe_email_institucional_quando_configurado(self):
        response = self.client.get(reverse("portal_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "atendimento@ncfly.com.br")
        self.assertContains(response, 'href="mailto:atendimento@ncfly.com.br"', html=False)

    @override_settings(PORTAL_COMPANY_CNPJ="66.162.952/0001-10")
    def test_rodapes_publicos_exibem_cnpj_quando_configurado(self):
        home_response = self.client.get(reverse("portal_home"))
        saas_response = self.client.get(reverse("portal_plataforma_saas"))

        self.assertEqual(home_response.status_code, 200)
        self.assertEqual(saas_response.status_code, 200)
        self.assertContains(home_response, "CNPJ: 66.162.952/0001-10.")
        self.assertContains(saas_response, "CNPJ: 66.162.952/0001-10.")

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

    def test_home_publica_exibe_bloco_de_alertas_por_email(self):
        response = self.client.get(reverse("portal_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quer receber novos alertas direto no seu e-mail?")
        self.assertContains(response, reverse("portal_termos_alertas_email"))

    def test_alertas_publicos_exibe_bloco_de_alertas_por_email(self):
        response = self.client.get(reverse("portal_alertas"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quer receber novos alertas?")
        self.assertNotContains(response, "Quer receber novos alertas direto no seu e-mail?")
        self.assertNotContains(response, "Cadastre seu contato para acompanhar novas oportunidades")
        self.assertContains(response, "Termos de Recebimento de Alertas")

    def test_detalhe_alerta_publico_carrega_com_cta_do_programa(self):
        Aeroporto.objects.create(
            nome="Aeroporto Internacional de Guarulhos",
            sigla="GRU",
            cidade="Sao Paulo",
            estado="SP",
        )
        Aeroporto.objects.create(
            nome="Miami International Airport",
            sigla="MIA",
            cidade="Miami",
            estado="FL",
        )
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
        self.assertContains(response, "Falar no WhatsApp")
        self.assertContains(response, "Como funciona")
        self.assertContains(response, "Aeroporto Internacional de Guarulhos - Sao Paulo")
        self.assertContains(response, "Miami International Airport - Miami")
        self.assertContains(response, 'class="portal-alert-detail__faq-item"', html=False)
        self.assertContains(
            response,
            "As datas e a disponibilidade desta oferta podem se esgotar rapidamente.",
        )
        self.assertContains(
            response,
            'data-whatsapp-message="Ol&aacute;! Vi o alerta GRU para MIA no portal NC Fly News e gostaria de fazer uma cota&ccedil;&atilde;o."',
            html=False,
        )
        self.assertContains(response, 'data-alert-link="', html=False)

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
            criado_em=timezone.now() - timedelta(days=16)
        )

        response = self.client.get(reverse("portal_alerta_detalhe", args=[alerta_antigo.id]))
        self.assertEqual(response.status_code, 404)

    def test_home_footer_publico_nao_exibe_links_juridicos_da_plataforma(self):
        response = self.client.get(reverse("portal_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sobre a NC Fly")
        self.assertContains(response, "Fale conosco")
        self.assertNotContains(response, "Termos da Plataforma")
        self.assertNotContains(response, "Privacidade da Plataforma")

    def test_pagina_saas_exibe_footer_proprio_sem_links_juridicos_da_plataforma(self):
        response = self.client.get(reverse("portal_plataforma_saas"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plataforma NC Fly")
        self.assertContains(response, "Perguntas frequentes")
        self.assertContains(response, "Fale conosco")
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
        self.assertContains(response, "Sobre a NC Fly")
        self.assertContains(response, "Fale conosco")
        self.assertContains(response, "Pol&iacute;tica de Privacidade")
        self.assertNotContains(response, "portal-deferred-section--md", html=False)

class PortalSeoTest(TestCase):
    def setUp(self):
        cache.clear()
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
        public_base_url = getattr(settings, "SITE_BASE_URL", "http://testserver").rstrip("/")
        response = self.client.get(reverse("portal_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<meta name="description"', html=False)
        self.assertContains(response, "SearchAction")
        self.assertContains(
            response,
            f'<link rel="canonical" href="{public_base_url}/home/">',
            html=False,
        )
        self.assertContains(response, 'property="og:title"', html=False)

    def test_detalhe_renderiza_schema_e_canonical(self):
        public_base_url = getattr(settings, "SITE_BASE_URL", "http://testserver").rstrip("/")
        response = self.client.get(self.noticia.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "application/ld+json")
        self.assertContains(response, "NewsArticle")
        self.assertContains(
            response,
            f'<link rel="canonical" href="{public_base_url}{self.noticia.get_absolute_url()}">',
            html=False,
        )

    def test_robots_txt_expoe_sitemap(self):
        public_base_url = getattr(settings, "SITE_BASE_URL", "http://testserver").rstrip("/")
        response = self.client.get(reverse("portal_robots"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User-agent: *")
        self.assertContains(response, f"Sitemap: {public_base_url}/sitemap.xml")

    def test_sitemap_xml_expoe_urls_publicas(self):
        response = self.client.get(reverse("portal_sitemap"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/home/")
        self.assertContains(response, "/home/alertas/")
        self.assertContains(response, "/home/alertas/termos-de-recebimento/")
        self.assertContains(response, "/home/fale-conosco/")
        self.assertContains(response, f"/home/alertas/{self.alerta.id}/")
        self.assertContains(response, "/home/plataforma/")
        self.assertNotContains(response, "/home/plataforma/contato/")
        self.assertContains(response, "/home/categorias/milhas-e-pontos/")
        self.assertContains(response, self.noticia.get_absolute_url())

    def test_sitemap_xml_mantem_alerta_publico_ate_quinze_dias(self):
        AlertaViagem.objects.filter(id=self.alerta.id).update(criado_em=timezone.now() - timedelta(days=10))
        self.alerta.refresh_from_db()

        response = self.client.get(reverse("portal_sitemap"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"/home/alertas/{self.alerta.id}/")


@override_settings(
    GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST123456",
    GOOGLE_SEARCH_CONSOLE_VERIFICATION="google-site-verification-token",
)
class PortalAnalyticsTest(TestCase):
    def setUp(self):
        cache.clear()
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

    def test_home_nao_carrega_script_adsense_no_html_inicial(self):
        response = self.client.get(reverse("portal_home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js")
        self.assertContains(response, 'data-ad-client="ca-pub-8670696864452622"', html=False)


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
        self.assertEqual(lead.aceite_versao, "2026-04-interesse-plataforma")
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


class PortalAlertEmailLeadTest(TestCase):
    def test_post_valido_na_home_cria_lead_de_alerta(self):
        response = self.client.post(
            reverse("portal_home"),
            data={
                "form_kind": "alert_email_lead",
                "nome_completo": "Ana Souza",
                "email": "ana@example.com",
                "telefone": "(11) 98888-7777",
                "aceite_alertas": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeadAlertaEmail.objects.count(), 1)
        lead = LeadAlertaEmail.objects.get()
        self.assertEqual(lead.nome_completo, "Ana Souza")
        self.assertEqual(lead.email, "ana@example.com")
        self.assertEqual(lead.telefone, "(11) 98888-7777")
        self.assertEqual(lead.origem_cadastro, "home")
        self.assertEqual(lead.aceite_versao, "2026-04-alertas-email")
        self.assertEqual(lead.status, "ativo")
        self.assertContains(response, "Seu contato entrou na lista.")

    def test_post_valido_formata_telefone_digitado_sem_mascara(self):
        response = self.client.post(
            reverse("portal_home"),
            data={
                "form_kind": "alert_email_lead",
                "nome_completo": "Ana Souza",
                "email": "ana@example.com",
                "telefone": "11988887777",
                "aceite_alertas": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        lead = LeadAlertaEmail.objects.get()
        self.assertEqual(lead.telefone, "(11) 98888-7777")

    def test_post_valido_na_pagina_de_alertas_cria_lead_de_alerta(self):
        response = self.client.post(
            reverse("portal_alertas"),
            data={
                "form_kind": "alert_email_lead",
                "nome_completo": "Bruno Lima",
                "email": "bruno@example.com",
                "telefone": "(21) 97777-6666",
                "aceite_alertas": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeadAlertaEmail.objects.count(), 1)
        lead = LeadAlertaEmail.objects.get()
        self.assertEqual(lead.origem_cadastro, "alertas")
        self.assertEqual(lead.source_environment, "local")
        self.assertEqual(lead.source_host, "testserver")
        self.assertContains(response, "Cadastro confirmado")

    def test_post_sem_aceite_nao_cria_lead_de_alerta(self):
        response = self.client.post(
            reverse("portal_alertas"),
            data={
                "form_kind": "alert_email_lead",
                "nome_completo": "Bruno Lima",
                "email": "bruno@example.com",
                "telefone": "(21) 97777-6666",
                "aceite_alertas": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeadAlertaEmail.objects.count(), 0)
        self.assertContains(response, "Você precisa aceitar os termos de recebimento de alertas")


    def test_post_com_email_ja_ativo_exibe_mensagem_de_cadastro_existente(self):
        LeadAlertaEmail.objects.create(
            nome_completo="Ana Souza",
            email="ana@example.com",
            telefone="(11) 98888-7777",
            origem_cadastro=LeadAlertaEmail.ORIGEM_HOME,
            aceite_versao="2026-04-alertas-email",
            status=LeadAlertaEmail.STATUS_ATIVO,
        )

        response = self.client.post(
            reverse("portal_home"),
            data={
                "form_kind": "alert_email_lead",
                "nome_completo": "Ana Souza",
                "email": "ana@example.com",
                "telefone": "(11) 98888-7777",
                "aceite_alertas": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeadAlertaEmail.objects.count(), 1)
        self.assertContains(response, "Este e-mail ja esta cadastrado para receber alertas.")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PORTAL_LEAD_NOTIFICATION_RECIPIENTS=["pdrnacari@gmail.com"],
)
class PortalLeadNotificationTest(TestCase):
    def setUp(self):
        mail.outbox = []

    def test_alert_email_signup_envia_notificacao_por_email(self):
        response = self.client.post(
            reverse("portal_home"),
            data={
                "form_kind": "alert_email_lead",
                "nome_completo": "Ana Souza",
                "email": "ana@example.com",
                "telefone": "(11) 98888-7777",
                "aceite_alertas": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["pdrnacari@gmail.com"])
        self.assertIn("alertas por e-mail", mail.outbox[0].subject)
        self.assertIn("Ana Souza", mail.outbox[0].body)
        self.assertIn("Home publica", mail.outbox[0].body)

    def test_plataforma_saas_envia_notificacao_por_email(self):
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
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["pdrnacari@gmail.com"])
        self.assertIn("Novo lead da plataforma", mail.outbox[0].subject)
        self.assertIn("Interesse rapido na landing da plataforma", mail.outbox[0].body)
        self.assertIn("maria@example.com", mail.outbox[0].body)

    def test_plataforma_contato_envia_notificacao_por_email(self):
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
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["pdrnacari@gmail.com"])
        self.assertIn("Novo lead da plataforma", mail.outbox[0].subject)
        self.assertIn("Formulario completo de contato da plataforma", mail.outbox[0].body)
        self.assertIn("Operadora Teste", mail.outbox[0].body)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_BASE_URL="https://ncfly.com.br",
    PORTAL_ALERTS_FROM_EMAIL="alertas@ncfly.com.br",
    PORTAL_ALERTS_REPLY_TO="atendimento@ncfly.com.br",
    PORTAL_CONTACT_WHATSAPP="12991722902",
)
class PortalAlertDigestTest(TestCase):
    def setUp(self):
        mail.outbox = []
        LeadAlertaEmail.objects.create(
            nome_completo="Ana Souza",
            email="ana@example.com",
            telefone="(11) 98888-7777",
            origem_cadastro=LeadAlertaEmail.ORIGEM_HOME,
            aceite_versao="2026-04-alertas-email",
            status=LeadAlertaEmail.STATUS_ATIVO,
        )
        LeadAlertaEmail.objects.create(
            nome_completo="Bruno Lima",
            email="bruno@example.com",
            telefone="(21) 97777-6666",
            origem_cadastro=LeadAlertaEmail.ORIGEM_ALERTAS,
            aceite_versao="2026-04-alertas-email",
            status=LeadAlertaEmail.STATUS_PAUSADO,
        )

    def _alerta_payload(self):
        return {
            "titulo": "GRU para MIA com milhas",
            "conteudo": "Nova oportunidade no site.",
            "continente": "América do Norte",
            "pais": "Estados Unidos",
            "cidade_destino": "Miami",
            "origem": "GRU",
            "destino": "MIA",
            "classe": AlertaViagem.CLASSE_ECONOMICA,
            "programa_fidelidade": "Smiles",
            "companhia_aerea": "American Airlines",
            "valor_milhas": 70000,
            "datas_ida": ["2026-06-01", "2026-06-03"],
            "datas_volta": ["2026-06-08"],
            "ativo": True,
        }

    def test_novo_alerta_publico_entra_na_fila_de_digest(self):
        _, created = create_or_update_alerta(self._alerta_payload())

        self.assertTrue(created)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AlertEmailDigestItem.objects.count(), 1)
        item = AlertEmailDigestItem.objects.get()
        self.assertEqual(item.kind, AlertEmailDigestItem.KIND_NEW)
        self.assertEqual(item.metadata_json["route_label"], "GRU para MIA")

    def test_atualizacao_antes_do_envio_atualiza_o_item_pendente(self):
        create_or_update_alerta(self._alerta_payload())

        payload = self._alerta_payload()
        payload["datas_ida"] = ["2026-06-01", "2026-06-03", "2026-06-05"]
        payload["datas_volta"] = ["2026-06-08", "2026-06-10"]

        _, created = create_or_update_alerta(payload)

        self.assertFalse(created)
        self.assertEqual(AlertEmailDigestItem.objects.count(), 1)
        item = AlertEmailDigestItem.objects.get()
        self.assertEqual(item.kind, AlertEmailDigestItem.KIND_NEW)
        self.assertEqual(item.sent_at, None)
        self.assertEqual(item.metadata_json["milhas_label"], "70.000 milhas")

    def test_reprocessamento_sem_mudanca_nao_cria_novo_item(self):
        create_or_update_alerta(self._alerta_payload())

        _, created = create_or_update_alerta(self._alerta_payload())

        self.assertFalse(created)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AlertEmailDigestItem.objects.count(), 1)

    def test_alerta_sem_milhas_nao_sobe_na_fila(self):
        payload = self._alerta_payload()
        payload["valor_milhas"] = None

        with self.assertRaisesMessage(ValueError, "Valor em milhas obrigatorio para publicar alerta."):
            create_or_update_alerta(payload)

        self.assertEqual(AlertEmailDigestItem.objects.count(), 0)

    def test_send_pending_alert_digest_envia_email_para_inscritos_ativos(self):
        alerta, _ = create_or_update_alerta(self._alerta_payload())

        result = send_pending_alert_digest()

        self.assertEqual(result["items"], 1)
        self.assertEqual(result["recipients"], 1)
        self.assertEqual(result["emails_sent"], 1)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["ana@example.com"])
        self.assertEqual(email.from_email, "alertas@ncfly.com.br")
        self.assertEqual(email.reply_to, ["atendimento@ncfly.com.br"])
        self.assertIn("1 atualização para conferir hoje", email.subject)
        self.assertIn(f"Ver alerta: https://ncfly.com.br/home/alertas/{alerta.id}/", email.body)
        self.assertIn(
            f"Compartilhar alerta: https://ncfly.com.br/home/alertas/{alerta.id}/compartilhar/",
            email.body,
        )
        self.assertIn("https://wa.me/5512991722902?text=", email.body)
        self.assertIn("Recebi%20o%20e-mail%20de%20alertas%20da%20NC%20Fly", email.body)
        self.assertIn("List-Unsubscribe", email.extra_headers)
        self.assertIn("/home/alertas/cancelar/?token=", email.extra_headers["List-Unsubscribe"])
        self.assertIn("Cancelar inscricao: https://ncfly.com.br/home/alertas/cancelar/?token=", email.body)
        self.assertEqual(len(email.alternatives), 1)
        self.assertEqual(email.alternatives[0][1], "text/html")
        self.assertIn("WhatsApp da NC Fly", email.alternatives[0][0])
        self.assertIn("Falar no WhatsApp", email.alternatives[0][0])
        self.assertIn("Compartilhar alerta", email.alternatives[0][0])
        self.assertIn(
            f'href="https://ncfly.com.br/home/alertas/{alerta.id}/compartilhar/"',
            email.alternatives[0][0],
        )
        self.assertIn("Cancelar inscricao", email.alternatives[0][0])
        self.assertIn('href="https://ncfly.com.br/home/alertas/cancelar/?token=', email.alternatives[0][0])

    def test_pagina_compartilhar_alerta_exibe_opcoes(self):
        alerta, _ = create_or_update_alerta(self._alerta_payload())

        response = self.client.get(reverse("portal_alerta_compartilhar", args=[alerta.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compartilhar agora")
        self.assertContains(response, "WhatsApp")
        self.assertContains(response, "Telegram")
        self.assertContains(response, "Copiar link")
        self.assertContains(response, f"/home/alertas/{alerta.id}/")

    def test_novo_inscrito_nao_recebe_digest_retroativo(self):
        create_or_update_alerta(self._alerta_payload())
        LeadAlertaEmail.objects.create(
            nome_completo="Carla Dias",
            email="carla@example.com",
            telefone="(31) 97777-5555",
            origem_cadastro=LeadAlertaEmail.ORIGEM_HOME,
            aceite_versao="2026-04-alertas-email",
            status=LeadAlertaEmail.STATUS_ATIVO,
        )

        result = send_pending_alert_digest()

        self.assertEqual(result["items"], 1)
        self.assertEqual(result["recipients"], 1)
        self.assertEqual(result["emails_sent"], 1)
        self.assertEqual({email.to[0] for email in mail.outbox}, {"ana@example.com"})

    def test_digest_sem_destinatario_elegivel_marca_item_como_processado(self):
        create_or_update_alerta(self._alerta_payload())
        LeadAlertaEmail.objects.all().delete()
        LeadAlertaEmail.objects.create(
            nome_completo="Carla Dias",
            email="carla@example.com",
            telefone="(31) 97777-5555",
            origem_cadastro=LeadAlertaEmail.ORIGEM_HOME,
            aceite_versao="2026-04-alertas-email",
            status=LeadAlertaEmail.STATUS_ATIVO,
        )

        result = send_pending_alert_digest()

        self.assertEqual(result["items"], 1)
        self.assertEqual(result["recipients"], 0)
        self.assertEqual(result["emails_sent"], 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AlertEmailDigestItem.objects.filter(sent_at__isnull=True).count(), 0)

    def test_send_pending_alert_digest_descarta_item_antigo_sem_milhas(self):
        alerta = AlertaViagem.objects.create(
            titulo="GRU para MIA sem milhas",
            conteudo="Alerta legado sem milhas.",
            continente="AmÃ©rica do Norte",
            pais="Estados Unidos",
            cidade_destino="Miami",
            origem="GRU",
            destino="MIA",
            classe=AlertaViagem.CLASSE_ECONOMICA,
            programa_fidelidade="Smiles",
            companhia_aerea="American Airlines",
            valor_milhas=None,
            datas_ida=["2026-06-01"],
            ativo=True,
        )
        AlertEmailDigestItem.objects.create(
            alerta=alerta,
            kind=AlertEmailDigestItem.KIND_NEW,
            metadata_json={"route_label": "GRU para MIA"},
        )

        result = send_pending_alert_digest()

        self.assertEqual(result["items"], 0)
        self.assertEqual(result["recipients"], 0)
        self.assertEqual(result["emails_sent"], 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AlertEmailDigestItem.objects.filter(sent_at__isnull=True).count(), 0)

    def test_send_pending_alert_digest_respeita_max_items_e_deixa_resto_para_depois(self):
        create_or_update_alerta(self._alerta_payload())
        payload = self._alerta_payload()
        payload["titulo"] = "GIG para JFK com milhas"
        payload["origem"] = "GIG"
        payload["destino"] = "JFK"
        payload["cidade_destino"] = "Nova York"
        payload["valor_milhas"] = 78000
        create_or_update_alerta(payload)

        result = send_pending_alert_digest(max_items=1)

        self.assertEqual(result["items"], 1)
        self.assertEqual(AlertEmailDigestItem.objects.filter(sent_at__isnull=True).count(), 1)
        self.assertEqual(AlertEmailDigestItem.objects.filter(sent_at__isnull=False).count(), 1)

    def test_send_pending_alert_digest_divide_por_janelas_restantes(self):
        for index in range(7):
            payload = self._alerta_payload()
            payload["titulo"] = f"Alerta {index}"
            payload["origem"] = "GRU" if index % 2 == 0 else "GIG"
            payload["destino"] = f"X{index:02d}"[:3]
            payload["cidade_destino"] = f"Destino {index}"
            payload["valor_milhas"] = 70000 + index
            create_or_update_alerta(payload)

        first = send_pending_alert_digest(remaining_slots=4)
        second = send_pending_alert_digest(remaining_slots=3)
        third = send_pending_alert_digest(remaining_slots=2)
        fourth = send_pending_alert_digest(remaining_slots=1)

        self.assertEqual(first["items"], 3)
        self.assertEqual(second["items"], 2)
        self.assertEqual(third["items"], 2)
        self.assertEqual(fourth["items"], 0)
        self.assertEqual(AlertEmailDigestItem.objects.filter(sent_at__isnull=True).count(), 0)

    def test_send_pending_alert_digest_pode_resolver_tudo_ate_meio_dia_quando_volume_for_baixo(self):
        for index in range(3):
            payload = self._alerta_payload()
            payload["titulo"] = f"Alerta leve {index}"
            payload["origem"] = "GRU" if index % 2 == 0 else "GIG"
            payload["destino"] = f"L{index:02d}"[:3]
            payload["cidade_destino"] = f"Destino leve {index}"
            payload["valor_milhas"] = 71000 + index
            create_or_update_alerta(payload)

        first = send_pending_alert_digest(remaining_slots=4)
        second = send_pending_alert_digest(remaining_slots=3)
        third = send_pending_alert_digest(remaining_slots=2)

        self.assertEqual(first["items"], 2)
        self.assertEqual(second["items"], 1)
        self.assertEqual(third["items"], 0)
        self.assertEqual(AlertEmailDigestItem.objects.filter(sent_at__isnull=True).count(), 0)

    def test_unsubscribe_endpoint_exibe_confirmacao_sem_descadastrar_no_get(self):
        lead = LeadAlertaEmail.objects.get(email="ana@example.com")
        token = build_alert_unsubscribe_token(lead.email)

        response = self.client.get(reverse("portal_alertas_unsubscribe"), {"token": token})

        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.status, LeadAlertaEmail.STATUS_ATIVO)
        self.assertContains(response, "Confirmar cancelamento")
        self.assertContains(response, "Recebo muitos e-mails")

    def test_unsubscribe_endpoint_confirma_cancelamento_com_motivo(self):
        lead = LeadAlertaEmail.objects.get(email="ana@example.com")
        token = build_alert_unsubscribe_token(lead.email)

        response = self.client.post(
            reverse("portal_alertas_unsubscribe"),
            {
                "token": token,
                "action": "confirm",
                "motivo": LeadAlertaEmail.MOTIVO_CANCELAMENTO_CONTEUDO_IRRELEVANTE,
            },
        )

        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.status, LeadAlertaEmail.STATUS_DESCADASTRADO)
        self.assertEqual(
            lead.motivo_cancelamento,
            LeadAlertaEmail.MOTIVO_CANCELAMENTO_CONTEUDO_IRRELEVANTE,
        )
        self.assertIsNotNone(lead.cancelado_em)
        self.assertContains(response, "Inscri")
        self.assertContains(response, "cancelada")

    def test_unsubscribe_endpoint_cancelar_mantem_lead_ativo(self):
        lead = LeadAlertaEmail.objects.get(email="ana@example.com")
        token = build_alert_unsubscribe_token(lead.email)

        response = self.client.post(
            reverse("portal_alertas_unsubscribe"),
            {
                "token": token,
                "action": "cancel",
            },
        )

        self.assertEqual(response.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.status, LeadAlertaEmail.STATUS_ATIVO)
        self.assertEqual(lead.motivo_cancelamento, "")
        self.assertIsNone(lead.cancelado_em)
        self.assertContains(response, "continua ativa")

    def test_unsubscribe_endpoint_token_invalido(self):
        response = self.client.get(reverse("portal_alertas_unsubscribe"), {"token": "invalido"})

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "link pode estar", status_code=400)


@override_settings(
    EMAIL_BACKEND="portal.email_backends.ResendEmailBackend",
    RESEND_API_KEY="re_test_123",
    RESEND_API_URL="https://api.resend.com/emails",
    RESEND_REQUEST_TIMEOUT=15,
    DEFAULT_FROM_EMAIL="pedro@ncfly.com.br",
)
class ResendEmailBackendTest(TestCase):
    @patch("portal.email_backends.requests.Session.post")
    def test_send_mail_via_resend_backend(self, mock_post):
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.raise_for_status = Mock()

        message = EmailMultiAlternatives(
            subject="Teste lead",
            body="Corpo simples",
            from_email="pedro@ncfly.com.br",
            to=["destino@example.com"],
        )

        sent = get_connection().send_messages([message])

        self.assertEqual(sent, 1)
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(mock_post.call_args.kwargs["timeout"], 15)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["from"], "pedro@ncfly.com.br")
        self.assertEqual(payload["to"], ["destino@example.com"])
        self.assertEqual(payload["subject"], "Teste lead")
        self.assertEqual(payload["text"], "Corpo simples")

    @patch("portal.email_backends.requests.Session.post")
    def test_email_multi_alternatives_preserva_html_headers_e_reply_to(self, mock_post):
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.raise_for_status = Mock()

        message = EmailMultiAlternatives(
            subject="Digest NC Fly",
            body="Versao texto",
            from_email="alertas@ncfly.com.br",
            to=["ana@example.com"],
            reply_to=["atendimento@ncfly.com.br"],
            headers={"List-Unsubscribe": "<https://ncfly.com.br/unsub>"},
        )
        message.attach_alternative("<p>Versao html</p>", "text/html")

        sent = get_connection().send_messages([message])

        self.assertEqual(sent, 1)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["reply_to"], ["atendimento@ncfly.com.br"])
        self.assertEqual(payload["headers"]["List-Unsubscribe"], "<https://ncfly.com.br/unsub>")
        self.assertEqual(payload["html"], "<p>Versao html</p>")
        self.assertEqual(payload["text"], "Versao texto")


class PortalArticleSeoMetadataTest(TestCase):
    def setUp(self):
        cache.clear()
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
        self.assertIn("Priorize um unico elemento hero", prompt)
        self.assertIn("Evite colagens genericas", prompt)
        self.assertIn("Sem texto, sem marcas d'agua", prompt)

    def test_render_svg_cover_quebra_titulo_em_linhas_e_escapa_caracteres(self):
        svg = _render_svg_cover(
            "BTG & TAP Black oferece at\u00e9 2 anos de anuidade gr\u00e1tis com condi\u00e7\u00f5es especiais e b\u00f4nus",
            "Promo\u00e7\u00f5es",
        ).decode("utf-8")
        self.assertIn("<tspan", svg)
        self.assertIn("&amp;", svg)
        self.assertIn("Imagem ilustrativa", svg)

    def test_detecta_marca_para_capa_padrao_da_noticia(self):
        theme = _resolve_cover_brand_theme(
            "Azul Viagens libera promocode FESTA10",
            "Campanha promocional da Azul Viagens com desconto em pacotes.",
            "",
            "Promocoes",
            "Ofertas Relampago",
            ["Azul Viagens"],
        )

        self.assertIsNotNone(theme)
        self.assertEqual(theme["label"], "Azul Viagens")

    def test_detecta_referencia_composta_para_capa_padrao_da_noticia(self):
        label = _extract_cover_brand_label(
            "Cartao XP Visa Infinite libera nova campanha com bonus de adesao.",
            "XP Visa Infinite com novos beneficios",
            "",
            "Cartoes de Credito",
        )
        theme = _resolve_cover_brand_theme(
            "Cartao XP Visa Infinite libera nova campanha com bonus de adesao.",
            "XP Visa Infinite com novos beneficios",
            "",
            "Cartoes de Credito",
            "Lancamentos e Analises",
            ["XP", "Visa Infinite"],
        )

        self.assertEqual(label, "XP Visa Infinite")
        self.assertIsNotNone(theme)
        self.assertEqual(theme["label"], "XP Visa Infinite")

    def test_cria_tema_generico_para_referencia_manual_fora_da_whitelist(self):
        label = _extract_cover_brand_label(
            "Campanha do cartao Inter Black garante beneficios extras para novos clientes.",
            "",
            "",
            "Cartoes de Credito",
        )
        theme = _resolve_cover_brand_theme(
            "Campanha do cartao Inter Black garante beneficios extras para novos clientes.",
            "",
            "",
            "Cartoes de Credito",
            "Lancamentos e Analises",
            ["Inter Black"],
        )

        self.assertEqual(label, "Inter Black")
        self.assertIsNotNone(theme)
        self.assertEqual(theme["label"], "Inter Black")
        self.assertEqual(theme["hint"], "Cartao em destaque")

    def test_portal_content_nao_transforma_asterisco_simples_em_negrito(self):
        rendered = str(portal_content("Linha com *marcacao simples* do Telegram."))

        self.assertIn("*marcacao simples*", rendered)
        self.assertNotIn("<strong>marcacao simples</strong>", rendered)

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


class PortalSingleUrlNewsSyncTest(TestCase):
    def setUp(self):
        self.source = Fonte.objects.create(
            nome="Fonte Manual Teste",
            url="https://example.com/",
            ativa=False,
            tipo_coleta="html",
            categoria_padrao="Milhas e Pontos",
        )

    @patch("portal.services.news_sync_service.ensure_cover_for_news", return_value=(None, False))
    @patch("portal.services.news_sync_service.build_news_draft")
    @patch("portal.services.news_sync_service.get_fetcher_for_source")
    def test_sync_news_from_url_publica_noticia_especifica(self, mock_get_fetcher, mock_build_news_draft, _mock_cover):
        from .services.news_sync_service import sync_news_from_url

        article = SimpleNamespace(
            url="https://example.com/2026/04/noticia-especifica",
            title="Titulo original da fonte",
            summary="Resumo original da fonte",
            text="Texto suficientemente longo para representar uma noticia valida. " * 8,
            html="<html><body>Conteudo</body></html>",
            image_url="",
            published_at=timezone.now(),
            metadata={"outbound_links": []},
        )
        mock_get_fetcher.return_value = SimpleNamespace(fetch_article=Mock(return_value=article))
        mock_build_news_draft.return_value = NewsDraft(
            titulo="Noticia publicada manualmente",
            resumo="Resumo reescrito para publicacao manual.",
            conteudo="Conteudo editorial reescrito a partir do link enviado no Telegram.",
            categoria="Milhas e Pontos",
            topico="Transferencias e Bonus",
            tags=["Milhas e Pontos", "Transferencias e Bonus"],
            cta_url="",
            cta_label="",
            slug="noticia-publicada-manualmente",
            confianca=Decimal("0.42"),
            imagem_url="",
            metadata={},
        )

        result = sync_news_from_url(article.url)

        self.assertEqual(result["outcome"], "published")
        noticia = NoticiaPublicada.objects.get()
        self.assertEqual(noticia.status, "published")
        self.assertEqual(noticia.titulo, "Noticia publicada manualmente")
        self.assertTrue(noticia.metadata_json.get("manual_submission"))

    @patch("portal.services.news_sync_service.ensure_cover_for_news", return_value=(None, False))
    @patch("portal.services.news_sync_service.build_news_draft")
    @patch("portal.services.news_sync_service.get_fetcher_for_source")
    def test_sync_news_from_url_atualiza_noticia_existente(self, mock_get_fetcher, mock_build_news_draft, _mock_cover):
        from .services.news_sync_service import sync_news_from_url

        article_url = "https://example.com/2026/04/noticia-especifica"
        raw_article = MateriaBruta.objects.create(
            fonte=self.source,
            url_original=article_url,
            titulo_extraido="Titulo antigo",
            texto_base="Texto antigo suficientemente longo para a noticia.",
            hash_conteudo="abc123",
        )
        noticia = NoticiaPublicada.objects.create(
            materia_bruta=raw_article,
            fonte=self.source,
            titulo="Titulo antigo publicado",
            resumo="Resumo antigo",
            conteudo="Conteudo antigo",
            categoria="Milhas e Pontos",
            topico="Transferencias e Bonus",
            tags_json=["Milhas e Pontos"],
            url_fonte=article_url,
            status="published",
            confianca=Decimal("0.90"),
            publicada_em=timezone.now() - timedelta(days=1),
        )

        article = SimpleNamespace(
            url=article_url,
            title="Titulo atualizado da fonte",
            summary="Resumo atualizado da fonte",
            text="Texto atualizado suficientemente longo para representar uma noticia valida. " * 8,
            html="<html><body>Conteudo novo</body></html>",
            image_url="",
            published_at=timezone.now(),
            metadata={"outbound_links": []},
        )
        mock_get_fetcher.return_value = SimpleNamespace(fetch_article=Mock(return_value=article))
        mock_build_news_draft.return_value = NewsDraft(
            titulo="Titulo atualizado publicado",
            resumo="Resumo atualizado",
            conteudo="Conteudo atualizado da noticia manual.",
            categoria="Milhas e Pontos",
            topico="Transferencias e Bonus",
            tags=["Milhas e Pontos", "Transferencias e Bonus"],
            cta_url="",
            cta_label="",
            slug="titulo-atualizado-publicado",
            confianca=Decimal("0.55"),
            imagem_url="",
            metadata={},
        )

        result = sync_news_from_url(article_url)

        self.assertEqual(result["outcome"], "updated")
        noticia.refresh_from_db()
        self.assertEqual(noticia.titulo, "Titulo atualizado publicado")
        self.assertTrue(noticia.metadata_json.get("manual_submission"))

    @patch("portal.services.news_sync_service.ensure_cover_for_news", return_value=(None, False))
    @patch("portal.services.news_sync_service.build_news_draft")
    def test_sync_news_from_text_publica_noticia_manual(self, mock_build_news_draft, _mock_cover):
        from .services.news_sync_service import sync_news_from_text

        raw_text = (
            "TEM PROMOCODE NOVO NO AR NESTE MES DE ANIVERSARIO DA AZUL VIAGENS. "
            "FESTA10 com 10% OFF em pacote aereo e hotel. "
            "Data de venda de 08/04/2026 a 21/04/2026. "
            "Data de viagem de 09/04/2026 a 27/06/2027. "
            "Regra juridica com condicoes detalhadas e aplicacao somente para pacote."
        )
        mock_build_news_draft.return_value = NewsDraft(
            titulo="Azul Viagens lanca promocode FESTA10 com 10% OFF em pacotes",
            resumo="Campanha promocional da Azul Viagens libera 10% de desconto em pacotes dentro do periodo informado.",
            conteudo="Conteudo editorial gerado a partir do texto enviado no Telegram.",
            categoria="Promocoes",
            topico="Ofertas Relampago",
            tags=["Promocoes", "Azul Viagens"],
            cta_url="",
            cta_label="",
            slug="azul-viagens-lanca-promocode-festa10",
            confianca=Decimal("0.61"),
            imagem_url="",
            metadata={},
        )

        result = sync_news_from_text(raw_text)

        self.assertEqual(result["outcome"], "published")
        noticia = NoticiaPublicada.objects.get()
        self.assertEqual(noticia.status, "published")
        self.assertEqual(noticia.categoria, "Promocoes")
        self.assertTrue(noticia.metadata_json.get("manual_submission"))

    @patch("portal.services.news_sync_service.ensure_cover_for_news", return_value=(None, False))
    @patch("portal.services.news_sync_service.build_news_draft")
    def test_sync_news_from_text_preserva_link_de_regulamento_como_cta(self, mock_build_news_draft, _mock_cover):
        from .services.news_sync_service import sync_news_from_text

        def fake_build_news_draft(_source_name, raw_article):
            return _apply_quality_rules(
                NewsDraft(
                    titulo="Azul Viagens libera promocode FESTA10 com 10% OFF em pacotes",
                    resumo="Campanha promocional da Azul Viagens com regulamento oficial disponivel.",
                    conteudo="Conteudo editorial gerado a partir do texto enviado no Telegram.",
                    categoria="Promocoes",
                    topico="Ofertas Relampago",
                    tags=["Promocoes", "Azul Viagens"],
                    cta_url="",
                    cta_label="",
                    slug="azul-viagens-festa10-regulamento",
                    confianca=Decimal("0.61"),
                    imagem_url="",
                    metadata={},
                ),
                raw_article,
            )

        mock_build_news_draft.side_effect = fake_build_news_draft

        raw_text = (
            "PROMOCAO DA AZUL VIAGENS COM CODIGO FESTA10 PARA PACOTES. "
            "Tipo de produto: Aereo Azul e Hotel. "
            "Regra juridica completa em https://azulviagens.com.br/termos-e-condicoes. "
            "Data de venda: 08/04/2026 a 21/04/2026."
        )

        result = sync_news_from_text(raw_text)

        self.assertEqual(result["outcome"], "published")
        noticia = NoticiaPublicada.objects.get()
        self.assertEqual(
            (noticia.metadata_json or {}).get("offer_cta", {}).get("url"),
            "https://azulviagens.com.br/termos-e-condicoes",
        )

    @patch("portal.services.news_sync_service.build_news_draft", side_effect=TimeoutError("timed out"))
    def test_sync_news_from_text_usa_fallback_local_quando_etapa_principal_falha(self, _mock_build_news_draft):
        from .services.news_sync_service import sync_news_from_text

        raw_text = (
            "TEM PROMOCODE NOVO NO AR NESTE MES DE ANIVERSARIO DA AZUL VIAGENS. "
            "FESTA10 com 10% OFF em pacote aereo e hotel. "
            "Tipo de produto: Aereo Azul, Aereo Amadeus, Hotel, Passeio, Traslado. "
            "Data de venda: 08/04/2026 a 21/04/2026. "
            "Data de viagem: 09/04/2026 a 27/06/2027. "
            "Regra juridica com condicoes completas da campanha."
        )

        result = sync_news_from_text(raw_text)

        self.assertEqual(result["outcome"], "published")
        noticia = NoticiaPublicada.objects.get()
        self.assertEqual(noticia.status, "published")
        self.assertIn("FESTA10", noticia.titulo)
        self.assertEqual(noticia.categoria, "Promoções")
        self.assertEqual(noticia.topico, "Ofertas Relâmpago")
        self.assertEqual(noticia.metadata_json.get("provider"), "manual_text_fallback")
        self.assertTrue(noticia.imagem.name.endswith(".svg"))
        self.assertFalse(noticia.imagem_url)
        self.assertNotIn("**", noticia.conteudo)
        with noticia.imagem.open("rb") as image_file:
            svg = image_file.read().decode("utf-8")
        self.assertIn("Azul Viagens", svg)

    @patch("portal.services.news_sync_service.ensure_cover_for_news", return_value=("portal/noticias/generated/manual-ai-cover.png", True))
    @patch("portal.services.news_sync_service.build_news_draft", side_effect=TimeoutError("timed out"))
    def test_sync_news_from_text_prioriza_capa_por_ia_no_fallback_manual(self, _mock_build_news_draft, mock_ensure_cover):
        from .services.news_sync_service import sync_news_from_text

        raw_text = (
            "CARTAO XP VISA INFINITE libera campanha especial para novos clientes. "
            "Tipo de produto: Cartao XP Visa Infinite. "
            "Data de venda: 10/04/2026 a 21/04/2026. "
            "Regra juridica: campanha valida para propostas aprovadas dentro do periodo e sujeita a analise de credito."
        )

        result = sync_news_from_text(raw_text)

        self.assertEqual(result["outcome"], "published")
        noticia = NoticiaPublicada.objects.get()
        self.assertEqual(noticia.imagem.name, "portal/noticias/generated/manual-ai-cover.png")
        self.assertEqual(noticia.metadata_json.get("cover_source"), "ai_generated")
        mock_ensure_cover.assert_called_once()

    @patch("portal.services.news_sync_service.build_news_draft", side_effect=TimeoutError("timed out"))
    def test_sync_news_from_text_gera_capa_contextual_com_programa_referenciado(self, _mock_build_news_draft):
        from .services.news_sync_service import sync_news_from_text

        raw_text = (
            "CARTAO XP VISA INFINITE libera campanha especial para novos clientes. "
            "Tipo de produto: Cartao XP Visa Infinite. "
            "Data de venda: 10/04/2026 a 21/04/2026. "
            "Regra juridica: campanha valida para propostas aprovadas dentro do periodo e sujeita a analise de credito."
        )

        result = sync_news_from_text(raw_text)

        self.assertEqual(result["outcome"], "published")
        noticia = NoticiaPublicada.objects.get()
        self.assertTrue(noticia.imagem.name.endswith(".svg"))
        with noticia.imagem.open("rb") as image_file:
            svg = image_file.read().decode("utf-8")
        self.assertIn("XP Visa Infinite", svg)

    @patch("portal.services.news_sync_service.build_news_draft", side_effect=TimeoutError("timed out"))
    def test_sync_news_from_text_atualiza_slug_quando_titulo_manual_melhora(self, _mock_build_news_draft):
        from .services.news_sync_service import sync_news_from_text

        raw_text = (
            "TEM PROMOCODE NOVO NO AR NESTE MES DE ANIVERSARIO DA AZUL VIAGENS. "
            "FESTA10 com 10% OFF em pacote aereo e hotel. "
            "Tipo de produto: Aereo Azul, Aereo Amadeus, Hotel, Passeio, Traslado. "
            "Data de venda: 08/04/2026 a 21/04/2026. "
            "Data de viagem: 09/04/2026 a 27/06/2027. "
            "Regra juridica com condicoes completas da campanha."
        )
        source = Fonte.objects.create(
            nome="Telegram Manual",
            url="https://ncfly.com.br/telegram/manual/",
            ativa=False,
            tipo_coleta="html",
            categoria_padrao="Promocoes",
        )
        pseudo_hash = hashlib.sha1(raw_text.encode("utf-8")).hexdigest()
        raw_article = MateriaBruta.objects.create(
            fonte=source,
            url_original=f"https://ncfly.com.br/telegram/manual/{pseudo_hash[:24]}/",
            titulo_extraido="Titulo antigo",
            texto_base=raw_text,
            hash_conteudo="manual-hash-1",
        )
        NoticiaPublicada.objects.create(
            materia_bruta=raw_article,
            fonte=source,
            titulo="Noticia NC Fly",
            resumo="Resumo antigo",
            conteudo="Conteudo antigo",
            slug="noticia-nc-fly",
            categoria="Promoções",
            topico="Ofertas Relâmpago",
            url_fonte=raw_article.url_original,
            status="published",
            confianca=Decimal("0.50"),
            publicada_em=timezone.now(),
        )

        result = sync_news_from_text(raw_text)

        self.assertEqual(result["outcome"], "updated")
        noticia = NoticiaPublicada.objects.get(materia_bruta=raw_article)
        self.assertEqual(noticia.titulo, "Azul Viagens libera cupom FESTA10 com 10% OFF em pacotes")
        self.assertNotEqual(noticia.slug, "noticia-nc-fly")
        self.assertIn("azul-viagens-libera-cupom-festa10", noticia.slug)


class PortalRegenerateNewsCoverCommandTest(TestCase):
    @patch(
        "portal.management.commands.regenerate_news_cover.ensure_cover_for_news",
        return_value=("portal/noticias/generated/capa-regenerada.png", True),
    )
    def test_regenera_capa_por_slug(self, _mock_cover):
        fonte = Fonte.objects.create(
            nome="Fonte Comando",
            url="https://example.com",
            tipo_coleta="html",
        )
        noticia = NoticiaPublicada.objects.create(
            fonte=fonte,
            titulo="Noticia com capa quebrada",
            resumo="Resumo suficiente para o teste do comando.",
            conteudo="Conteudo suficiente para representar uma noticia ja publicada.",
            slug="noticia-com-capa-quebrada",
            categoria="Promocoes",
            topico="Ofertas Relampago",
            tags_json=["Promocoes", "Azul Viagens"],
            url_fonte="https://example.com/noticia",
            imagem_url="https://example.com/imagem-quebrada.jpg",
            status="published",
            confianca=Decimal("0.85"),
            publicada_em=timezone.now(),
            metadata_json={"offer_cta": {"url": "https://example.com/regulamento", "label": "Ver regras"}},
        )

        stdout = StringIO()
        call_command("regenerate_news_cover", noticia.slug, stdout=stdout)

        noticia.refresh_from_db()
        self.assertEqual(noticia.imagem.name, "portal/noticias/generated/capa-regenerada.png")
        self.assertTrue(noticia.imagem_ilustrativa)
        self.assertEqual(noticia.metadata_json.get("cover_source"), "ai_generated")
        self.assertEqual(noticia.imagem_url, "https://example.com/imagem-quebrada.jpg")
        self.assertIn("Capa regenerada com sucesso.", stdout.getvalue())


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
        cache.clear()
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


class PortalCrossSourceDeduplicationTest(TestCase):
    def setUp(self):
        cache.clear()
        self.fonte = Fonte.objects.create(nome="Fonte Espelho", url="https://espelho.com", tipo_coleta="html")
        self.materia = MateriaBruta.objects.create(
            fonte=self.fonte,
            url_original="https://espelho.com/noticia",
            titulo_extraido="Campanha de transferencia com bonus de 30 por cento",
            texto_base=(
                "Clientes elegiveis podem transferir pontos com bonus de 30 por cento ate o fim da semana. "
                "A oferta vale no programa parceiro informado na campanha oficial."
            ),
            hash_conteudo="hash-espelho",
            metadata_json={
                "outbound_links": [
                    {"url": "https://programa.exemplo.com/promocao?utm_source=espelho", "label": "Aproveitar"}
                ]
            },
        )
        metadata = append_source_reference(
            {
                "story_fingerprint": build_story_fingerprint(
                    "Campanha de transferencia com bonus de 30 por cento",
                    "Oferta promocional para clientes elegiveis no programa parceiro.",
                    "Promocoes",
                    "Transferencias e Bonus",
                    self.materia.texto_base,
                )
            },
            source_name="Fonte Espelho",
            article_url="https://espelho.com/noticia",
            title="Campanha de transferencia com bonus de 30 por cento",
        )
        self.noticia = NoticiaPublicada.objects.create(
            materia_bruta=self.materia,
            fonte=self.fonte,
            titulo="Campanha de transferencia com bonus de 30 por cento",
            resumo="Oferta promocional para clientes elegiveis no programa parceiro.",
            conteudo="Conteudo editorial publicado no portal a partir da primeira fonte.",
            slug="campanha-transferencia-bonus-30",
            categoria="Promocoes",
            topico="Transferencias e Bonus",
            tags_json=["Promocoes", "Transferencias e Bonus"],
            url_fonte="https://espelho.com/noticia",
            status="published",
            metadata_json=metadata,
        )

    def test_find_duplicate_news_detecta_mesma_pauta_por_corpo_e_link_de_saida(self):
        duplicate = find_duplicate_news(
            "Banco libera acao especial para enviar pontos ao programa",
            "Promocao libera bonus de 30 por cento nas transferencias por tempo limitado.",
            "Promocoes",
            "Transferencias e Bonus",
            body=(
                "Clientes elegiveis podem transferir pontos com bonus de 30 por cento ate o fim da semana. "
                "A oferta vale no programa parceiro informado na campanha oficial."
            ),
            outbound_urls=["https://programa.exemplo.com/promocao?utm_medium=email"],
        )
        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate.pk, self.noticia.pk)

    def test_append_source_reference_ignora_variacao_de_tracking_na_mesma_url(self):
        metadata = append_source_reference(
            {},
            source_name="Fonte A",
            article_url="https://a.com/noticia?utm_source=fonte-a",
            title="Titulo",
        )
        metadata = append_source_reference(
            metadata,
            source_name="Fonte B",
            article_url="https://a.com/noticia?utm_medium=email",
            title="Titulo",
        )
        self.assertEqual(len(metadata["source_references"]), 1)

    def test_find_duplicate_news_manual_submission_e_mais_conservador(self):
        duplicate = find_duplicate_news(
            "Banco premium libera nova campanha institucional",
            "Nova acao comercial para clientes de alta renda com foco em posicionamento de marca.",
            "Promocoes",
            "Transferencias e Bonus",
            body=(
                "Texto editorial sobre posicionamento de marca, beneficios amplos e campanha comercial sem relacao direta "
                "com a transferencia bonificada da noticia publicada anteriormente."
            ),
            outbound_urls=["https://programa.exemplo.com/promocao?utm_source=manual"],
            source_url="https://fonte-nova.com/noticia-diferente",
            manual_submission=True,
        )

        self.assertIsNone(duplicate)

    def test_find_duplicate_news_manual_submission_aceita_mesma_url_original(self):
        duplicate = find_duplicate_news(
            "Titulo qualquer",
            "Resumo qualquer",
            "Promocoes",
            "Transferencias e Bonus",
            body="Outro corpo qualquer.",
            source_url="https://espelho.com/noticia",
            manual_submission=True,
        )

        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate.pk, self.noticia.pk)

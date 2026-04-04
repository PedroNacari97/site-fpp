from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from gestao.models import Aeroporto, AlertaViagem
from gestao.services.alerta_parser import parse_alerta_bruto


RAW_ALERT = """
:flag-br: Ribeirão Preto (RAO) 3.928 Milhas + taxas
Econômica

:black_small_square: Programa LatamPass
Custo trecho: 3.928 milhas + taxas
:black_small_square: Classe Econômica
:black_small_square: Voando Latam

:airplane_departure: São Paulo (GRU) > Ribeirão Preto (RAO)

:date: Disponibilidade de Ida
Jun/26:`01,02,03,04,05,06`

:airplane_departure: Ribeirão Preto (RAO) > São Paulo (GRU)

:date: Disponibilidade de Volta
Jun/26:`03,04,05,06,07,09,11`

Pesquisar ida e volta para achar esses valores.

:eagle:@falcaodasmilhas
:warning: Datas para disponibilidades de pelo menos 01 assento por voo, a partir de 02 assentos as disponibilidades de datas serão menores.
:warning: Os valores e disponibilidade enviados esgotam-se rápido!
""".strip()


class AlertaParserTest(TestCase):
    def setUp(self):
        Aeroporto.objects.create(
            sigla="GRU",
            nome="Guarulhos",
            cidade="São Paulo",
            estado="SP",
        )
        Aeroporto.objects.create(
            sigla="RAO",
            nome="Ribeirão Preto (Leite Lopes)",
            cidade="Ribeirão Preto",
            estado="N/A",
        )

    def test_parse_alerta_bruto_extracts_main_fields(self):
        parsed = parse_alerta_bruto(RAW_ALERT)

        self.assertEqual(parsed["destino"], "RAO")
        self.assertEqual(parsed["origem"], "GRU")
        self.assertEqual(parsed["cidade_destino"], "Ribeirão Preto")
        self.assertEqual(parsed["pais"], "Brasil")
        self.assertEqual(parsed["continente"], "América do Sul")
        self.assertEqual(parsed["classe"], AlertaViagem.CLASSE_ECONOMICA)
        self.assertEqual(parsed["programa_fidelidade"], "LatamPass")
        self.assertEqual(parsed["companhia_aerea"], "LATAM")
        self.assertEqual(parsed["valor_milhas"], "3928")
        self.assertEqual(parsed["datas_ida"][0], "2026-06-01")
        self.assertEqual(parsed["datas_volta"][-1], "2026-06-11")

    def test_parse_alerta_bruto_uses_custo_trecho_when_first_line_has_no_milhas(self):
        raw_alert = """
        :flag-br: Ribeirão Preto (RAO)
        Econômica

        Programa LatamPass
        Custo trecho: 4.100 milhas + taxas
        Classe Econômica
        Voando Latam

        São Paulo (GRU) > Ribeirão Preto (RAO)
        """.strip()

        parsed = parse_alerta_bruto(raw_alert)

        self.assertEqual(parsed["valor_milhas"], "4100")
        self.assertIn("a partir de 4.100 milhas + taxas", parsed["titulo"].lower())


class AlertaAutopreenchimentoViewTest(TestCase):
    def setUp(self):
        Aeroporto.objects.create(
            sigla="RAO",
            nome="Ribeirão Preto (Leite Lopes)",
            cidade="Ribeirão Preto",
            estado="SP",
        )
        self.user = get_user_model().objects.create_superuser(
            username="root",
            email="root@example.com",
            password="secret123",
        )
        self.client.force_login(self.user)

    def test_autopreencher_populates_form_without_saving(self):
        response = self.client.post(
            reverse("admin_alerta_passagem_novo"),
            {
                "alerta_bruto": RAW_ALERT,
                "autopreencher": "1",
                "titulo": "",
                "conteudo": "",
                "continente": "",
                "pais": "",
                "cidade_destino": "",
                "origem": "",
                "destino": "",
                "classe": "",
                "programa_fidelidade": "",
                "companhia_aerea": "",
                "valor_milhas": "",
                "valor_reais": "",
                "datas_ida": "[]",
                "datas_volta": "[]",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Campos preenchidos a partir do alerta bruto")
        form = response.context["form"]
        self.assertEqual(form["origem"].value(), "GRU")
        self.assertEqual(form["destino"].value(), "RAO")
        self.assertEqual(form["programa_fidelidade"].value(), "LatamPass")
        self.assertEqual(AlertaViagem.objects.count(), 0)

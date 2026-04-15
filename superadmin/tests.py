"""
Testes do modulo superadmin.

Cobre:
- Mixin/decorator de acesso: bloqueia usuarios nao-superadmin, permite o superadmin
- Views de dashboard, noticias e empresas: status codes e redirecionamentos
- Exclusao de noticia: GET (confirmacao) e POST (exclusao + redirect)
- Criacao de empresa via POST
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from gestao.models import Empresa
from portal.models import NoticiaPublicada

User = get_user_model()

SUPERADMIN_EMAIL = "pedro@ncfly.com.br"


def make_superadmin(**kwargs):
    defaults = {
        "username": "superadmin_test",
        "email": SUPERADMIN_EMAIL,
        "is_staff": True,
        "is_superuser": True,
    }
    defaults.update(kwargs)
    user = User(**defaults)
    user.set_password("senha_test_123")
    user.save()
    return user


def make_regular_user(**kwargs):
    defaults = {
        "username": "usuario_comum",
        "email": "outro@exemplo.com",
    }
    defaults.update(kwargs)
    user = User(**defaults)
    user.set_password("senha_comum_456")
    user.save()
    return user


# ---------------------------------------------------------------------------
# Mixin de acesso
# ---------------------------------------------------------------------------

class SuperAdminMixinAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.regular = make_regular_user()
        self.dashboard_url = reverse("superadmin_dashboard")

    def test_anonimo_redireciona_para_login(self):
        resp = self.client.get(self.dashboard_url)
        self.assertIn(resp.status_code, [301, 302])

    def test_usuario_comum_recebe_403(self):
        self.client.force_login(self.regular)
        resp = self.client.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 403)

    def test_superadmin_acessa_dashboard(self):
        self.client.force_login(self.superadmin)
        resp = self.client.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.client.force_login(self.superadmin)

    def test_dashboard_retorna_200(self):
        resp = self.client.get(reverse("superadmin_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dashboard")

    def test_dashboard_exibe_metricas(self):
        NoticiaPublicada.objects.create(
            titulo="Noticia teste",
            resumo="resumo",
            conteudo="conteudo",
            url_fonte="https://exemplo.com",
            status="published",
        )
        resp = self.client.get(reverse("superadmin_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("total_noticias", resp.context)
        self.assertGreaterEqual(resp.context["total_noticias"], 1)


# ---------------------------------------------------------------------------
# Noticias
# ---------------------------------------------------------------------------

class NoticiasListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.client.force_login(self.superadmin)
        self.url = reverse("superadmin_noticias_list")

    def test_lista_retorna_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_filtro_por_status(self):
        NoticiaPublicada.objects.create(
            titulo="Publicada",
            resumo="r",
            conteudo="c",
            url_fonte="https://a.com",
            status="published",
        )
        NoticiaPublicada.objects.create(
            titulo="Rascunho",
            resumo="r",
            conteudo="c",
            url_fonte="https://b.com",
            status="draft",
        )
        resp = self.client.get(self.url + "?status=published")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["total"], 1)


class NoticiaDeleteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.client.force_login(self.superadmin)
        self.noticia = NoticiaPublicada.objects.create(
            titulo="Para deletar",
            resumo="r",
            conteudo="c",
            url_fonte="https://delete.com",
            status="draft",
        )

    def test_get_exibe_confirmacao(self):
        url = reverse("superadmin_noticia_delete", kwargs={"pk": self.noticia.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Para deletar")

    def test_post_exclui_e_redireciona(self):
        pk = self.noticia.pk
        url = reverse("superadmin_noticia_delete", kwargs={"pk": pk})
        resp = self.client.post(url)
        self.assertRedirects(resp, reverse("superadmin_noticias_list"))
        self.assertFalse(NoticiaPublicada.objects.filter(pk=pk).exists())

    def test_get_nao_exclui(self):
        """Um GET na URL de delete nao deve excluir a noticia."""
        pk = self.noticia.pk
        url = reverse("superadmin_noticia_delete", kwargs={"pk": pk})
        self.client.get(url)
        self.assertTrue(NoticiaPublicada.objects.filter(pk=pk).exists())


# ---------------------------------------------------------------------------
# Artigo upload
# ---------------------------------------------------------------------------

class ArtigoUploadViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.client.force_login(self.superadmin)
        self.url = reverse("superadmin_artigo_upload")

    def test_get_retorna_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_post_valido_cria_noticia(self):
        total_antes = NoticiaPublicada.objects.count()
        resp = self.client.post(self.url, {
            "titulo": "Artigo manual de teste",
            "resumo": "Resumo do artigo",
            "conteudo": "Conteudo completo aqui.",
            "url_fonte": "https://fonte.com/artigo",
            "status": "draft",
        })
        self.assertRedirects(resp, reverse("superadmin_noticias_list"))
        self.assertEqual(NoticiaPublicada.objects.count(), total_antes + 1)
        noticia = NoticiaPublicada.objects.latest("criada_em")
        self.assertEqual(noticia.titulo, "Artigo manual de teste")
        self.assertEqual(noticia.status, "draft")

    def test_post_sem_titulo_retorna_form_com_erro(self):
        resp = self.client.post(self.url, {
            "titulo": "",
            "resumo": "r",
            "conteudo": "c",
            "url_fonte": "https://x.com",
            "status": "draft",
        })
        self.assertEqual(resp.status_code, 200)
        msgs = list(resp.wsgi_request._messages)
        self.assertTrue(any("Titulo" in str(m) for m in msgs))


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------

class EmpresasListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.client.force_login(self.superadmin)
        self.url = reverse("superadmin_empresas_list")

    def test_lista_retorna_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)


class EmpresaCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superadmin = make_superadmin()
        self.client.force_login(self.superadmin)
        self.url = reverse("superadmin_empresa_create")

    def test_get_retorna_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_post_valido_cria_empresa(self):
        total_antes = Empresa.objects.count()
        resp = self.client.post(self.url, {
            "nome": "Agencia Teste NCfly",
            "responsavel_nome": "Fulano",
            "email_contato": "contato@agencia.com",
            "telefone_contato": "11999999999",
            "limite_colaboradores": "5",
            "ativo": "1",
        })
        self.assertEqual(Empresa.objects.count(), total_antes + 1)
        empresa = Empresa.objects.get(nome="Agencia Teste NCfly")
        self.assertRedirects(resp, reverse("superadmin_empresa_detail", kwargs={"pk": empresa.pk}))

    def test_post_sem_nome_retorna_erro(self):
        resp = self.client.post(self.url, {
            "nome": "",
            "limite_colaboradores": "0",
        })
        self.assertEqual(resp.status_code, 200)
        msgs = list(resp.wsgi_request._messages)
        self.assertTrue(any("Nome" in str(m) for m in msgs))

    def test_post_nome_duplicado_retorna_erro(self):
        Empresa.objects.create(nome="Duplicada")
        resp = self.client.post(self.url, {
            "nome": "Duplicada",
            "limite_colaboradores": "0",
            "ativo": "1",
        })
        self.assertEqual(resp.status_code, 200)
        msgs = list(resp.wsgi_request._messages)
        self.assertTrue(any("Duplicada" in str(m) for m in msgs))


# ---------------------------------------------------------------------------
# Adapter do allauth
# ---------------------------------------------------------------------------

class SuperadminAdapterTest(TestCase):
    """Testa a logica do adapter sem depender do fluxo OAuth completo."""

    def test_is_superadmin_true_para_email_correto(self):
        from superadmin.mixins import _is_superadmin
        user = make_superadmin()
        self.assertTrue(_is_superadmin(user))

    def test_is_superadmin_false_para_outro_email(self):
        from superadmin.mixins import _is_superadmin
        user = make_regular_user()
        self.assertFalse(_is_superadmin(user))

    def test_is_superadmin_false_para_anonimo(self):
        from superadmin.mixins import _is_superadmin
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(_is_superadmin(AnonymousUser()))

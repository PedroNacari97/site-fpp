from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from gestao.models import (
    AceiteDocumentoPlataforma,
    Cliente,
    DocumentoPlataforma,
    Empresa,
)


User = get_user_model()


class PlatformLegalAcceptanceFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin-empresa-legal",
            password="secret123",
            email="admin@empresa.com",
            first_name="Admin",
            last_name="Empresa",
        )
        self.empresa = Empresa.objects.create(nome="Empresa Legal")
        self.cliente = Cliente.objects.create(
            usuario=self.user,
            empresa=self.empresa,
            telefone="11999999999",
            cpf="12345678901",
            perfil="admin",
            ativo=True,
        )
        self.empresa.admin = self.cliente
        self.empresa.save(update_fields=["admin"])

    def test_admin_empresa_e_redirecionado_para_aceite_quando_ha_pendencia(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("portal_aceite_plataforma")))

    def test_aceite_registra_empresa_usuario_ip_e_versao(self):
        self.client.force_login(self.user)
        documentos = list(
            DocumentoPlataforma.objects.filter(ativo=True, exige_aceite_empresa=True)
        )
        payload = {
            "next": reverse("admin_dashboard"),
            "platform_accept": "1",
            "device_type": "desktop",
            "browser_name": "Chrome",
            "browser_version": "135.0",
            "os_name": "Windows",
            "os_version": "11",
            "device_language": "pt-BR",
            "device_timezone": "America/Sao_Paulo",
            "screen_resolution": "1920x1080",
            "geolocation_status": "granted",
            "latitude": "-23.550520",
            "longitude": "-46.633308",
            "geolocation_accuracy_meters": "120.50",
        }

        response = self.client.post(
            reverse("portal_aceite_plataforma"),
            data=payload,
            REMOTE_ADDR="10.20.30.40",
            HTTP_USER_AGENT="codex-test-agent",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_dashboard"))
        self.assertEqual(
            AceiteDocumentoPlataforma.objects.filter(empresa=self.empresa).count(),
            len(documentos),
        )
        aceite = AceiteDocumentoPlataforma.objects.filter(empresa=self.empresa).first()
        self.assertEqual(aceite.aceito_por, self.user)
        self.assertEqual(aceite.ip_aceite, "10.20.30.40")
        self.assertTrue(aceite.versao_aceita)
        self.assertEqual(aceite.device_type, "desktop")
        self.assertEqual(aceite.browser_name, "Chrome")
        self.assertEqual(aceite.os_name, "Windows")
        self.assertEqual(str(aceite.latitude), "-23.550520")
        self.assertEqual(str(aceite.longitude), "-46.633308")
        self.assertEqual(str(aceite.geolocation_accuracy_meters), "120.50")

    def test_admin_empresa_acessa_dashboard_normalmente_depois_do_aceite(self):
        self.client.force_login(self.user)
        for documento in DocumentoPlataforma.objects.filter(ativo=True, exige_aceite_empresa=True):
            AceiteDocumentoPlataforma.objects.create(
                empresa=self.empresa,
                documento=documento,
                versao_aceita=documento.versao_atual,
                aceito_por=self.user,
            )

        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_pagina_de_aceite_exibe_coleta_tecnica_e_localizacao_opcional(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("portal_aceite_plataforma"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Metadados do aceite")
        self.assertContains(response, "Localizacao opcional no momento do aceite")

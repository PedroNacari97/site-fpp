from datetime import date

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_documentos_plataforma(apps, schema_editor):
    DocumentoPlataforma = apps.get_model("gestao", "DocumentoPlataforma")
    defaults = [
        ("platform_terms", "v1.0", True),
        ("platform_privacy", "v1.0", True),
        ("platform_dpa", "v1.0", True),
        ("platform_security", "v1.0", True),
    ]
    for tipo, versao, exige_aceite in defaults:
        DocumentoPlataforma.objects.update_or_create(
            tipo=tipo,
            defaults={
                "versao_atual": versao,
                "data_vigencia": date(2026, 4, 3),
                "exige_aceite_empresa": exige_aceite,
                "ativo": True,
                "observacoes_internas": "",
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0047_cotacaovoo_duracao_fuso"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentoPlataforma",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("platform_terms", "Termos da Plataforma"), ("platform_privacy", "Privacidade da Plataforma"), ("platform_dpa", "DPA / Aditivo de Tratamento de Dados"), ("platform_security", "Politica de Seguranca / Uso Aceitavel")], max_length=40, unique=True)),
                ("versao_atual", models.CharField(default="v1.0", max_length=30)),
                ("data_vigencia", models.DateField(default=date.today)),
                ("exige_aceite_empresa", models.BooleanField(default=True)),
                ("ativo", models.BooleanField(default=True)),
                ("observacoes_internas", models.TextField(blank=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Documento da plataforma",
                "verbose_name_plural": "Documentos da plataforma",
                "ordering": ["tipo"],
            },
        ),
        migrations.CreateModel(
            name="AceiteDocumentoPlataforma",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("versao_aceita", models.CharField(max_length=30)),
                ("aceito_em", models.DateTimeField(auto_now_add=True)),
                ("ip_aceite", models.CharField(blank=True, max_length=45)),
                ("user_agent_aceite", models.CharField(blank=True, max_length=255)),
                ("aceito_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="aceites_documentos_plataforma", to=settings.AUTH_USER_MODEL)),
                ("documento", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="aceites", to="gestao.documentoplataforma")),
                ("empresa", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="aceites_documentos_plataforma", to="gestao.empresa")),
            ],
            options={
                "verbose_name": "Aceite de documento da plataforma",
                "verbose_name_plural": "Aceites de documentos da plataforma",
                "ordering": ["-aceito_em"],
            },
        ),
        migrations.AddConstraint(
            model_name="aceitedocumentoplataforma",
            constraint=models.UniqueConstraint(fields=("empresa", "documento", "versao_aceita"), name="unique_aceite_documento_empresa_versao"),
        ),
        migrations.RunPython(seed_documentos_plataforma, migrations.RunPython.noop),
    ]

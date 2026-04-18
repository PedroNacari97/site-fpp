# Portal B2C — contas isoladas + opt-ins granulares (alertas/artigos)
# Gerada manualmente — NAO mexer em migrations ja aplicadas.

from django.db import migrations, models
import django.db.models.deletion

import portal.models as portal_models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0013_fix_buscado_em_nullable"),
    ]

    operations = [
        # 1) destaque_home no ModuloEstudo — controla o modulo de amostra aberto na home
        migrations.AddField(
            model_name="moduloestudo",
            name="destaque_home",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text=(
                    "Se marcado, aparece como módulo de amostra aberto na home "
                    "pública (apenas 1 deve ficar marcado)"
                ),
            ),
        ),

        # 2) PortalUser — conta de usuario B2C, SEM ligacao com auth.User
        migrations.CreateModel(
            name="PortalUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254, unique=True)),
                ("nome", models.CharField(blank=True, max_length=180)),
                ("senha_hash", models.CharField(blank=True, default="", max_length=256)),
                ("google_sub", models.CharField(blank=True, db_index=True, default="", help_text="Google account 'sub' (ID estavel) — unico por usuario Google", max_length=64)),
                ("email_verificado", models.BooleanField(db_index=True, default=False)),
                ("ativo", models.BooleanField(db_index=True, default=True)),
                ("ip_cadastro", models.CharField(blank=True, default="", max_length=45)),
                ("user_agent_cadastro", models.CharField(blank=True, default="", max_length=255)),
                ("source_environment", models.CharField(db_index=True, default="local", max_length=20)),
                ("source_host", models.CharField(blank=True, db_index=True, max_length=120)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("ultimo_login_em", models.DateTimeField(blank=True, null=True)),
                ("ultimo_login_ip", models.CharField(blank=True, default="", max_length=45)),
            ],
            options={
                "verbose_name": "Usuario do portal B2C",
                "verbose_name_plural": "Usuarios do portal B2C",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.AddConstraint(
            model_name="portaluser",
            constraint=models.UniqueConstraint(
                fields=("google_sub",),
                name="unique_portal_user_google_sub",
                condition=models.Q(google_sub__gt=""),
            ),
        ),

        # 3) OptInAlertaPassagem — consentimento granular para alertas
        migrations.CreateModel(
            name="OptInAlertaPassagem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("ativo", models.BooleanField(db_index=True, default=True)),
                ("token_unsubscribe", models.CharField(default=portal_models._gen_unsubscribe_token, max_length=64, unique=True)),
                ("aceite_versao", models.CharField(blank=True, default="", max_length=40)),
                ("aceite_hash_documento", models.CharField(blank=True, default="", max_length=64)),
                ("aceito_em", models.DateTimeField(blank=True, null=True)),
                ("aceito_ip", models.CharField(blank=True, default="", max_length=45)),
                ("aceito_user_agent", models.CharField(blank=True, default="", max_length=255)),
                ("cancelado_em", models.DateTimeField(blank=True, null=True)),
                ("cancelado_ip", models.CharField(blank=True, default="", max_length=45)),
                ("motivo_cancelamento", models.CharField(blank=True, default="", max_length=80)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="portal.portaluser")),
            ],
            options={
                "verbose_name": "Opt-in de alerta de passagem",
                "verbose_name_plural": "Opt-ins de alertas de passagens",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.AddConstraint(
            model_name="optinalertapassagem",
            constraint=models.UniqueConstraint(fields=("user",), name="unique_optin_alerta_passagem_por_user"),
        ),

        # 4) OptInArtigoNovo — consentimento granular para notificacao de artigo
        migrations.CreateModel(
            name="OptInArtigoNovo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("ativo", models.BooleanField(db_index=True, default=True)),
                ("token_unsubscribe", models.CharField(default=portal_models._gen_unsubscribe_token, max_length=64, unique=True)),
                ("aceite_versao", models.CharField(blank=True, default="", max_length=40)),
                ("aceite_hash_documento", models.CharField(blank=True, default="", max_length=64)),
                ("aceito_em", models.DateTimeField(blank=True, null=True)),
                ("aceito_ip", models.CharField(blank=True, default="", max_length=45)),
                ("aceito_user_agent", models.CharField(blank=True, default="", max_length=255)),
                ("cancelado_em", models.DateTimeField(blank=True, null=True)),
                ("cancelado_ip", models.CharField(blank=True, default="", max_length=45)),
                ("motivo_cancelamento", models.CharField(blank=True, default="", max_length=80)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="portal.portaluser")),
            ],
            options={
                "verbose_name": "Opt-in de artigo novo",
                "verbose_name_plural": "Opt-ins de artigos novos",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.AddConstraint(
            model_name="optinartigonovo",
            constraint=models.UniqueConstraint(fields=("user",), name="unique_optin_artigo_novo_por_user"),
        ),
    ]

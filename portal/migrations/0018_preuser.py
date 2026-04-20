"""PreUser — tracking de visitantes anonimos do portal (conversao)."""
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0017_aceite_url_origem"),
    ]

    operations = [
        migrations.CreateModel(
            name="PreUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uid", models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ("primeiro_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("primeiro_ua", models.TextField(blank=True)),
                ("primeira_url", models.URLField(blank=True, max_length=500)),
                ("primeiro_referrer", models.URLField(blank=True, max_length=500)),
                ("utm_source", models.CharField(blank=True, max_length=120)),
                ("utm_medium", models.CharField(blank=True, max_length=120)),
                ("utm_campaign", models.CharField(blank=True, max_length=120)),
                ("ultimo_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("ultima_url", models.URLField(blank=True, max_length=500)),
                ("ultima_visita_em", models.DateTimeField(auto_now=True)),
                ("total_visitas", models.PositiveIntegerField(default=1)),
                ("convertido_em", models.DateTimeField(blank=True, null=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "portal_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pre_users",
                        to="portal.portaluser",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pre-user (visitante anonimo)",
                "verbose_name_plural": "Pre-users (visitantes anonimos)",
            },
        ),
        migrations.AddIndex(
            model_name="preuser",
            index=models.Index(
                fields=["portal_user", "convertido_em"],
                name="portal_preu_portal__7cf3a6_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="preuser",
            index=models.Index(
                fields=["-criado_em"],
                name="portal_preu_criado__c3961b_idx",
            ),
        ),
    ]

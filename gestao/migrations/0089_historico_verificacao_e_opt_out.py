import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def _preencher_opt_out_tokens(apps, schema_editor):
    Model = apps.get_model("gestao", "AcompanhamentoPassagem")
    for obj in Model.objects.all():
        obj.opt_out_token = uuid.uuid4()
        obj.save(update_fields=["opt_out_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0088_companhiaaerea_codigo"),
    ]

    operations = [
        migrations.AddField(
            model_name="acompanhamentopassagem",
            name="notificar_passageiro",
            field=models.BooleanField(
                default=True,
                help_text="Se desmarcado, mudanças de status não disparam email para o passageiro.",
            ),
        ),
        migrations.AddField(
            model_name="acompanhamentopassagem",
            name="opt_out_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(_preencher_opt_out_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="acompanhamentopassagem",
            name="opt_out_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.CreateModel(
            name="HistoricoVerificacao",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "verificado_em",
                    models.DateTimeField(db_index=True, default=timezone.now),
                ),
                ("sucesso", models.BooleanField(default=False)),
                ("duracao_ms", models.PositiveIntegerField(default=0)),
                ("status_reserva_anterior", models.CharField(blank=True, max_length=24)),
                ("status_voo_anterior", models.CharField(blank=True, max_length=24)),
                ("status_reserva_novo", models.CharField(blank=True, max_length=24)),
                ("status_voo_novo", models.CharField(blank=True, max_length=24)),
                ("mudou_desde_anterior", models.BooleanField(default=False)),
                ("notificacao_disparada", models.BooleanField(default=False)),
                ("payload_sanitizado", models.JSONField(blank=True, default=dict)),
                ("erro_mensagem", models.TextField(blank=True)),
                ("scraper_nome", models.CharField(blank=True, max_length=40)),
                (
                    "acompanhamento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="historico",
                        to="gestao.acompanhamentopassagem",
                    ),
                ),
            ],
            options={
                "ordering": ["-verificado_em"],
                "indexes": [
                    models.Index(
                        fields=["acompanhamento", "-verificado_em"], name="hv_acomp_data_idx"
                    ),
                    models.Index(
                        fields=["mudou_desde_anterior", "-verificado_em"], name="hv_mudou_data_idx"
                    ),
                ],
            },
        ),
    ]

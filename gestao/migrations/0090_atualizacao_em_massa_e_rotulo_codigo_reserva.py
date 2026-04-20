import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def _set_rotulo_latam(apps, schema_editor):
    CompanhiaAerea = apps.get_model("gestao", "CompanhiaAerea")
    for cia in CompanhiaAerea.objects.all():
        codigo = (cia.codigo or "").upper()
        nome = (cia.nome or "").lower()
        if codigo == "LATAM" or "latam" in nome:
            if cia.rotulo_codigo_reserva != "Nº da Ordem":
                cia.rotulo_codigo_reserva = "Nº da Ordem"
                cia.save(update_fields=["rotulo_codigo_reserva"])


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0089_historico_verificacao_e_opt_out"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="companhiaaerea",
            name="rotulo_codigo_reserva",
            field=models.CharField(
                default="Código da Reserva",
                help_text="Como o operador chama o código da reserva no portal desta companhia. LATAM usa 'Nº da Ordem'.",
                max_length=40,
                verbose_name="Rótulo do código de reserva",
            ),
        ),
        migrations.RunPython(_set_rotulo_latam, _noop_reverse),
        migrations.CreateModel(
            name="AtualizacaoEmMassa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("iniciado_em", models.DateTimeField(db_index=True, default=timezone.now)),
                ("concluido_em", models.DateTimeField(blank=True, null=True)),
                ("total", models.PositiveIntegerField(default=0)),
                ("ok", models.PositiveIntegerField(default=0)),
                ("sem_mudanca", models.PositiveIntegerField(default=0)),
                ("com_mudanca", models.PositiveIntegerField(default=0)),
                ("erro", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("em_andamento", "Em andamento"),
                            ("concluido", "Concluído"),
                            ("interrompido", "Interrompido"),
                            ("erro", "Erro"),
                        ],
                        db_index=True,
                        default="em_andamento",
                        max_length=20,
                    ),
                ),
                ("resultado", models.JSONField(blank=True, default=list)),
                ("mensagem_erro", models.TextField(blank=True)),
                (
                    "empresa",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="atualizacoes_em_massa",
                        to="gestao.empresa",
                    ),
                ),
                (
                    "iniciado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="atualizacoes_em_massa_iniciadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Atualização em massa",
                "verbose_name_plural": "Atualizações em massa",
                "ordering": ["-iniciado_em"],
            },
        ),
        migrations.AddIndex(
            model_name="atualizacaoemmassa",
            index=models.Index(fields=["empresa", "-iniciado_em"], name="gestao_atua_empresa_6d73d5_idx"),
        ),
        migrations.AddIndex(
            model_name="atualizacaoemmassa",
            index=models.Index(fields=["status", "iniciado_em"], name="gestao_atua_status_2eba48_idx"),
        ),
    ]

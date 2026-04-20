from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0091_cliente_passaporte_cliente_passaporte_validade_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="acompanhamentopassagem",
            name="codigo_reserva_portal",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Código de reserva (PNR de 6 dígitos) devolvido pelo portal da "
                    "companhia. Para LATAM, o ``localizador_consulta`` guarda o Nº "
                    "da Ordem (LA…IWSR) e este campo guarda o reloc."
                ),
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="acompanhamentopassagem",
            name="status_reserva",
            field=models.CharField(
                choices=[
                    ("nao_iniciado", "Nao iniciado"),
                    ("aguardando_consulta", "Aguardando consulta"),
                    ("reservado", "Reservado"),
                    ("emitido", "Emitido"),
                    ("programado", "Programado"),
                    ("ticketado", "Ticketado"),
                    ("alterado", "Alterado"),
                    ("cancelado", "Cancelado"),
                    ("embarcado", "Embarcado"),
                    ("concluido", "Concluido"),
                    ("inconsistente", "Inconsistente"),
                ],
                default="nao_iniciado",
                max_length=24,
            ),
        ),
    ]

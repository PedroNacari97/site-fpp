from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0032_emissor_parceiro_usuario"),
    ]

    operations = [
        migrations.AddField(
            model_name="emissaopassagem",
            name="valor_total_final",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0035_emissaopassagem_custo_emissor_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="emissorparceiro",
            name="telefone",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]

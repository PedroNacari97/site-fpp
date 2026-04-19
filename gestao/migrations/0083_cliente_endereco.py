from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0082_notificacao_sistema_tipo_arquivada"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="cep",
            field=models.CharField(blank=True, max_length=9),
        ),
        migrations.AddField(
            model_name="cliente",
            name="endereco",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="cliente",
            name="numero",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="cliente",
            name="complemento",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="cliente",
            name="bairro",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="cliente",
            name="cidade",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="cliente",
            name="estado",
            field=models.CharField(blank=True, max_length=2),
        ),
    ]

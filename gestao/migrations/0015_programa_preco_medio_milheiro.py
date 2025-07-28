from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0014_aeroporto_remove_emissaopassagem_aeroporto_ida_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="programafidelidade",
            name="preco_medio_milheiro",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AlterField(
            model_name="cliente",
            name="perfil",
            field=models.CharField(
                choices=[
                    ("admin", "Administrador"),
                    ("operador", "Operador"),
                    ("cliente", "Cliente"),
                ],
                default="cliente",
                max_length=10,
            ),
        ),
    ]
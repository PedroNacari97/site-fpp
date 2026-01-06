from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0019_remove_emissaopassagem_descricao"),
    ]

    operations = [
        migrations.CreateModel(
            name="Empresa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=150, unique=True)),
                ("limite_colaboradores", models.PositiveIntegerField(default=0)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(default=django.utils.timezone.now)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Empresa",
                "verbose_name_plural": "Empresas",
                "ordering": ["nome"],
            },
        ),
        migrations.AddField(
            model_name="cliente",
            name="empresa",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pessoas",
                to="gestao.empresa",
            ),
        ),
        migrations.AddField(
            model_name="empresa",
            name="admin",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="empresa_administrada",
                to="gestao.cliente",
            ),
        ),
    ]
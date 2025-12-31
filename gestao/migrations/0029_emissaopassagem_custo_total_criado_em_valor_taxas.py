from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('gestao', '0028_emissor_parceiro_cpfs'),
    ]

    operations = [
        migrations.RenameField(
            model_name='emissaopassagem',
            old_name='valor_pago',
            new_name='valor_taxas',
        ),
        migrations.AddField(
            model_name='emissaopassagem',
            name='custo_total',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='emissaopassagem',
            name='criado_em',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]

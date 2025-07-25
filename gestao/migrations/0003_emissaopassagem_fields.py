from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('gestao', '0002_cliente_cpf_cliente_perfil'),
    ]

    operations = [
        migrations.AddField(
            model_name='emissaopassagem',
            name='aeroporto_ida',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='emissaopassagem',
            name='aeroporto_volta',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='emissaopassagem',
            name='data_ida',
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name='emissaopassagem',
            name='data_volta',
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name='emissaopassagem',
            name='qtd_passageiros',
            field=models.PositiveIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='emissaopassagem',
            name='valor_referencia',
            field=models.DecimalField(decimal_places=2, max_digits=10, default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='emissaopassagem',
            name='valor_pago',
            field=models.DecimalField(decimal_places=2, max_digits=10, default=0),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='emissaopassagem',
            name='pontos_utilizados',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='emissaopassagem',
            name='valor_referencia_pontos',
            field=models.DecimalField(blank=True, null=True, decimal_places=2, max_digits=10),
        ),
        migrations.AlterField(
            model_name='emissaopassagem',
            name='economia_obtida',
            field=models.DecimalField(blank=True, null=True, decimal_places=2, max_digits=10),
        ),
        migrations.AlterField(
            model_name='emissaopassagem',
            name='programa',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, to='gestao.programafidelidade'),
        ),
    ]
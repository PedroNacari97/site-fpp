from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0081_mover_acessos_para_programa_sala_vip"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificacaosistema",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("cotacao_nova", "Novas cotações"),
                    ("cotacao_aprovada", "Cotações aprovadas"),
                    ("cotacao_vencendo", "Cotações vencendo"),
                    ("emissao_concluida", "Emissões concluídas"),
                    ("emissao_pendente", "Emissões pendentes"),
                    ("alerta_passagem", "Alertas de passagem"),
                    ("cliente_cadastrado", "Clientes cadastrados"),
                    ("clube_vencendo", "Clubes vencendo"),
                    ("saldo_baixo", "Saldos baixos"),
                    ("sistema", "Sistema"),
                    ("outros", "Outros"),
                ],
                db_index=True,
                default="outros",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="notificacaosistema",
            name="url_acao",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="notificacaosistema",
            name="arquivada_em",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddIndex(
            model_name="notificacaosistema",
            index=models.Index(
                fields=["usuario", "lida", "arquivada_em"],
                name="ns_usuario_lida_arq_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificacaosistema",
            index=models.Index(
                fields=["tipo", "criado_em"],
                name="ns_tipo_criado_idx",
            ),
        ),
    ]

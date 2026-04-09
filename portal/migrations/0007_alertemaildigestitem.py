from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0058_telegramnoticiaevento"),
        ("portal", "0006_leadalertaemail"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlertEmailDigestItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("new", "Novo alerta"), ("updated", "Alerta atualizado")], default="new", max_length=20)),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("sent_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("alerta", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="alert_email_digest_items", to="gestao.alertaviagem")),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="noticiapublicada",
            name="tags_json",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="noticiapublicada",
            name="topico",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddIndex(
            model_name="noticiapublicada",
            index=models.Index(fields=["status", "categoria", "topico"], name="portal_noti_status_81dad4_idx"),
        ),
    ]

from django.db import migrations, models


def backfill_local_environment(apps, schema_editor):
    PortalMetricDaily = apps.get_model("portal", "PortalMetricDaily")
    LeadPlataforma = apps.get_model("portal", "LeadPlataforma")
    PortalMetricDaily.objects.update(site_environment="local", site_host="localhost")
    LeadPlataforma.objects.update(source_environment="local", source_host="localhost")


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0004_leadplataforma"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalmetricdaily",
            name="site_environment",
            field=models.CharField(db_index=True, default="local", max_length=20),
        ),
        migrations.AddField(
            model_name="portalmetricdaily",
            name="site_host",
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
        migrations.AddField(
            model_name="leadplataforma",
            name="source_environment",
            field=models.CharField(db_index=True, default="local", max_length=20),
        ),
        migrations.AddField(
            model_name="leadplataforma",
            name="source_host",
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
        migrations.RunPython(backfill_local_environment, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="portalmetricdaily",
            name="portal_metric_daily_unique_bucket",
        ),
        migrations.AddConstraint(
            model_name="portalmetricdaily",
            constraint=models.UniqueConstraint(
                fields=(
                    "metric_date",
                    "site_environment",
                    "site_host",
                    "metric_type",
                    "path",
                    "event_name",
                    "section",
                    "article_slug",
                    "article_category",
                    "article_topic",
                ),
                name="portal_metric_daily_unique_bucket_env",
            ),
        ),
    ]

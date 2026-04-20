from django.db import migrations, models


URL_HELP = "URL absoluta onde o aceite foi registrado (evidencia forense LGPD)"
URL_OPTIN_HELP = "URL absoluta onde o opt-in foi registrado (evidencia forense LGPD)"


class Migration(migrations.Migration):

    dependencies = [
        (
            "portal",
            "0016_rename_portal_prog_user_id_artigo_idx_portal_prog_user_id_2d139c_idx_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="leadplataforma",
            name="aceito_url_origem",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                help_text=URL_HELP,
            ),
        ),
        migrations.AddField(
            model_name="leadalertaemail",
            name="aceito_url_origem",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                help_text=URL_HELP,
            ),
        ),
        migrations.AddField(
            model_name="optinalertapassagem",
            name="aceito_url_origem",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                help_text=URL_OPTIN_HELP,
            ),
        ),
        migrations.AddField(
            model_name="optinartigonovo",
            name="aceito_url_origem",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                help_text=URL_OPTIN_HELP,
            ),
        ),
    ]

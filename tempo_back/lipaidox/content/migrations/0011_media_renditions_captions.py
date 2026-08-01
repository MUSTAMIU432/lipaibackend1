from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lipaidox_content", "0010_contentattachment_description_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentmedia",
            name="renditions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="contentmedia",
            name="captions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="contentattachment",
            name="renditions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="contentattachment",
            name="captions",
            field=models.JSONField(blank=True, default=list),
        ),
    ]

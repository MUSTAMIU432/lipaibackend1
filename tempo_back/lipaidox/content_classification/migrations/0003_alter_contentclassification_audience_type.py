# Generated manually — store multiple audience slugs (|||-joined, max 3 on API).

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lipaidox_cc", "0002_contentclassification_target_age_gap_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contentclassification",
            name="audience_type",
            field=models.TextField(blank=True, default="general"),
        ),
    ]

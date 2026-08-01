from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lipaidox_creator_profile", "0006_follow_follow_unique_follow_per_tenant"),
    ]

    operations = [
        migrations.AlterField(
            model_name="creatorprofile",
            name="area_of_interest",
            field=models.TextField(blank=True, null=True),
        ),
    ]

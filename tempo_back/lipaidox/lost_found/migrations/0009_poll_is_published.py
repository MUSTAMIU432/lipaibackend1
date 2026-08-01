from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lost_found", "0008_add_answer_parent_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="communitypoll",
            name="is_published",
            field=models.BooleanField(default=True),
        ),
    ]

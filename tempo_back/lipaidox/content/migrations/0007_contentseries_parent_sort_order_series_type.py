# Generated manually — model had parent/sort_order/series_type but DB table lacked columns.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("lipaidox_content", "0006_contentappeal"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentseries",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sub_series",
                to="lipaidox_content.contentseries",
            ),
        ),
        migrations.AddField(
            model_name="contentseries",
            name="sort_order",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="contentseries",
            name="series_type",
            field=models.CharField(
                choices=[
                    ("collection", "Collection/Course"),
                    ("chapter", "Chapter"),
                    ("sub_topic", "Sub-Topic"),
                ],
                default="collection",
                max_length=20,
            ),
        ),
    ]

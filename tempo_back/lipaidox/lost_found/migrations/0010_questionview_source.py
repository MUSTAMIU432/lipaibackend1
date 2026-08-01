from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lost_found", "0009_poll_is_published"),
    ]

    operations = [
        migrations.AddField(
            model_name="questionview",
            name="source",
            field=models.CharField(
                choices=[("profile", "Profile"), ("feed", "Feed"), ("direct", "Direct"), ("other", "Other")],
                default="other",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="questionview",
            name="is_follower",
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name="questionview",
            index=models.Index(fields=["question", "source"], name="comm_qview_q_source_idx"),
        ),
        migrations.AddIndex(
            model_name="questionview",
            index=models.Index(fields=["question", "viewed_at"], name="comm_qview_q_viewed_idx"),
        ),
    ]

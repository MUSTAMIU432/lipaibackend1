from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("lipaidox", "0001_initial"),
        ("lipaidox_content", "0011_media_renditions_captions"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentReview",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("rating", models.PositiveSmallIntegerField()),
                ("title", models.CharField(blank=True, default="", max_length=120)),
                ("body", models.TextField()),
                ("status", models.CharField(choices=[("published", "Published"), ("hidden", "Hidden"), ("flagged", "Flagged"), ("rejected", "Rejected")], default="published", max_length=20)),
                ("is_verified", models.BooleanField(default=False)),
                ("helpful_count", models.IntegerField(default=0)),
                ("edited_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="content_reviews", to=settings.AUTH_USER_MODEL)),
                ("content", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="lipaidox_content.content")),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_instances", to="lipaidox.tenant")),
            ],
            options={"db_table": "content_reviews"},
        ),
        migrations.CreateModel(
            name="ContentReviewHelpful",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("review", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="helpful_marks", to="lipaidox_content.contentreview")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="content_review_helpful_marks", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_instances", to="lipaidox.tenant")),
            ],
            options={"db_table": "content_review_helpful_marks"},
        ),
        migrations.AddIndex(model_name="contentreview", index=models.Index(fields=["content"], name="creview_content_idx")),
        migrations.AddIndex(model_name="contentreview", index=models.Index(fields=["author"], name="creview_author_idx")),
        migrations.AddIndex(model_name="contentreview", index=models.Index(fields=["status"], name="creview_status_idx")),
        migrations.AddIndex(model_name="contentreview", index=models.Index(fields=["rating"], name="creview_rating_idx")),
        migrations.AddIndex(model_name="contentreview", index=models.Index(fields=["created_at"], name="creview_created_idx")),
        migrations.AddIndex(model_name="contentreview", index=models.Index(fields=["content", "status", "created_at"], name="creview_content_status_cr_idx")),
        migrations.AddConstraint(model_name="contentreview", constraint=models.UniqueConstraint(fields=("author", "content", "tenant"), name="unique_content_review_per_tenant")),
        migrations.AddIndex(model_name="contentreviewhelpful", index=models.Index(fields=["review"], name="creview_help_review_idx")),
        migrations.AddIndex(model_name="contentreviewhelpful", index=models.Index(fields=["user"], name="creview_help_user_idx")),
        migrations.AddConstraint(model_name="contentreviewhelpful", constraint=models.UniqueConstraint(fields=("review", "user"), name="unique_content_review_helpful")),
    ]

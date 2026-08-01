from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("lipaidox", "0001_initial"),
        ("lipaidox_creator_profile", "0007_alter_creatorprofile_area_of_interest"),
    ]

    operations = [
        migrations.CreateModel(
            name="MembershipSubscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("active", "Active"), ("cancelled", "Cancelled")], default="active", max_length=20)),
                ("notification_preference", models.CharField(choices=[("all", "All"), ("personalized", "Personalized"), ("none", "None")], default="personalized", max_length=20)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subscriber", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="membership_subscriptions", to=settings.AUTH_USER_MODEL)),
                ("target", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="member_subscriptions", to="lipaidox_creator_profile.creatorprofile")),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_instances", to="lipaidox.tenant")),
            ],
            options={"db_table": "membership_subscriptions"},
        ),
        migrations.CreateModel(
            name="Review",
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
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="authored_reviews", to=settings.AUTH_USER_MODEL)),
                ("target", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="lipaidox_creator_profile.creatorprofile")),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_instances", to="lipaidox.tenant")),
            ],
            options={"db_table": "creator_reviews"},
        ),
        migrations.CreateModel(
            name="ReviewHelpful",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("review", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="helpful_marks", to="lipaidox_creator_profile.review")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="review_helpful_marks", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_instances", to="lipaidox.tenant")),
            ],
            options={"db_table": "review_helpful_marks"},
        ),
        migrations.CreateModel(
            name="ReviewReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="review_reports", to=settings.AUTH_USER_MODEL)),
                ("review", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="lipaidox_creator_profile.review")),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_instances", to="lipaidox.tenant")),
            ],
            options={"db_table": "review_reports"},
        ),
        migrations.AddIndex(model_name="membershipsubscription", index=models.Index(fields=["subscriber"], name="member_sub_subscr_idx")),
        migrations.AddIndex(model_name="membershipsubscription", index=models.Index(fields=["target"], name="member_sub_target_idx")),
        migrations.AddIndex(model_name="membershipsubscription", index=models.Index(fields=["status"], name="member_sub_status_idx")),
        migrations.AddIndex(model_name="membershipsubscription", index=models.Index(fields=["subscriber", "created_at"], name="member_sub_subscr_cr_idx")),
        migrations.AddIndex(model_name="membershipsubscription", index=models.Index(fields=["target", "created_at"], name="member_sub_target_cr_idx")),
        migrations.AddIndex(model_name="membershipsubscription", index=models.Index(fields=["subscriber", "target"], name="member_sub_pair_idx")),
        migrations.AddConstraint(model_name="membershipsubscription", constraint=models.UniqueConstraint(fields=("subscriber", "target", "tenant"), name="unique_membership_per_tenant")),
        migrations.AddIndex(model_name="review", index=models.Index(fields=["target"], name="review_target_idx")),
        migrations.AddIndex(model_name="review", index=models.Index(fields=["author"], name="review_author_idx")),
        migrations.AddIndex(model_name="review", index=models.Index(fields=["status"], name="review_status_idx")),
        migrations.AddIndex(model_name="review", index=models.Index(fields=["rating"], name="review_rating_idx")),
        migrations.AddIndex(model_name="review", index=models.Index(fields=["created_at"], name="review_created_idx")),
        migrations.AddIndex(model_name="review", index=models.Index(fields=["target", "status", "created_at"], name="review_target_status_cr_idx")),
        migrations.AddConstraint(model_name="review", constraint=models.UniqueConstraint(fields=("author", "target", "tenant"), name="unique_review_per_tenant")),
        migrations.AddIndex(model_name="reviewhelpful", index=models.Index(fields=["review"], name="review_help_review_idx")),
        migrations.AddIndex(model_name="reviewhelpful", index=models.Index(fields=["user"], name="review_help_user_idx")),
        migrations.AddConstraint(model_name="reviewhelpful", constraint=models.UniqueConstraint(fields=("review", "user"), name="unique_review_helpful")),
        migrations.AddIndex(model_name="reviewreport", index=models.Index(fields=["review"], name="review_report_review_idx")),
    ]

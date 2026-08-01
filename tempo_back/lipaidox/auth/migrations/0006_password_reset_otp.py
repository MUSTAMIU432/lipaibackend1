# Generated manually for PasswordResetOtp

import uuid
from datetime import timedelta

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone as django_timezone


def _default_otp_expiry():
    return django_timezone.now() + timedelta(minutes=10)


class Migration(migrations.Migration):
    dependencies = [
        ("lipaidox_auth", "0005_alter_user_apple_id_alter_user_google_id_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordResetOtp",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("code_hash", models.CharField(max_length=128)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("used", "Used"),
                            ("expired", "Expired"),
                            ("superseded", "Superseded"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                (
                    "expires_at",
                    models.DateTimeField(default=_default_otp_expiry),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="password_reset_otps",
                        to="lipaidox_auth.user",
                    ),
                ),
            ],
            options={
                "db_table": "password_reset_otps",
            },
        ),
        migrations.AddIndex(
            model_name="passwordresetotp",
            index=models.Index(
                fields=["user", "status"],
                name="pwreset_otp_user_status_idx",
            ),
        ),
    ]

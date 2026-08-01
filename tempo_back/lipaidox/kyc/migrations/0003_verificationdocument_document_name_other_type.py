from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lipaidox_kyc", "0002_businessverification"),
    ]

    operations = [
        # Extend document_type choices to include 'other'
        migrations.AlterField(
            model_name="verificationdocument",
            name="document_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("passport", "Passport"),
                    ("national_id", "National ID"),
                    ("driver_license", "Driver License"),
                    ("other", "Other"),
                ],
                max_length=50,
                null=True,
            ),
        ),
        # Free-text document name for 'other' type
        migrations.AddField(
            model_name="verificationdocument",
            name="document_name",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]

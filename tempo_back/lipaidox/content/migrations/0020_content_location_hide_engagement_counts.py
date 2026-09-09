from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lipaidox_content', '0019_contentview_contentview_unique_view_per_user_content'),
    ]

    operations = [
        migrations.AddField(
            model_name='content',
            name='location',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='content',
            name='hide_engagement_counts',
            field=models.BooleanField(default=False),
        ),
    ]

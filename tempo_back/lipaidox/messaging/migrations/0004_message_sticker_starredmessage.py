from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('lipaidox', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('lipaidox_messaging', '0003_conversation_cleared_at_creator_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='sticker',
            field=models.CharField(blank=True, max_length=16, null=True),
        ),
        migrations.CreateModel(
            name='StarredMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stars', to='lipaidox_messaging.message')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_instances', to='lipaidox.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='starred_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'starred_messages',
                'indexes': [models.Index(fields=['user'], name='idx_starred_messages_user')],
                'unique_together': {('message', 'user')},
            },
        ),
    ]

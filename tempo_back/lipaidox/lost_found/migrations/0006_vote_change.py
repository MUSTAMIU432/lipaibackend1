import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('lost_found', '0005_question_votes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. allow_vote_change on CommunityPoll
        #    Default True; model.save() forces False on verified_only / hide_results_until_close.
        migrations.AddField(
            model_name='communitypoll',
            name='allow_vote_change',
            field=models.BooleanField(default=True),
        ),

        # 2. change_count on CommunityPollVote — times this vote has been changed
        migrations.AddField(
            model_name='communitypollvote',
            name='change_count',
            field=models.PositiveIntegerField(default=0),
        ),

        # 3. last_changed_at on CommunityPollVote — for cooldown enforcement
        migrations.AddField(
            model_name='communitypollvote',
            name='last_changed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),

        # 4. VoteChange audit-log table (append-only; user identity never exposed via API)
        migrations.CreateModel(
            name='VoteChange',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ('poll', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vote_changes',
                    to='lost_found.communitypoll',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='poll_vote_changes',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('from_option', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    related_name='+',
                    to='lost_found.polloption',
                )),
                ('to_option', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    related_name='+',
                    to='lost_found.polloption',
                )),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'community_poll_vote_changes',
                'ordering': ['-changed_at'],
            },
        ),

        # 5. Index for fast audit queries and per-user-per-poll lookups
        migrations.AddIndex(
            model_name='votechange',
            index=models.Index(
                fields=['poll', 'user', 'changed_at'],
                name='vpc_poll_user_time_idx',
            ),
        ),
    ]

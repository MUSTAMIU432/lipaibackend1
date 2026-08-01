import uuid
from django.db import migrations, models
import django.db.models.deletion


def migrate_options_forward(apps, schema_editor):
    """
    Create PollOption rows from the legacy options JSONField, then point every
    CommunityPollVote at the corresponding PollOption row via the new option FK.
    """
    CommunityPoll = apps.get_model('lost_found', 'CommunityPoll')
    PollOption = apps.get_model('lost_found', 'PollOption')
    CommunityPollVote = apps.get_model('lost_found', 'CommunityPollVote')

    for poll in CommunityPoll.objects.all():
        raw_options = poll.options or []
        created_options = []
        for i, opt in enumerate(raw_options):
            po = PollOption.objects.create(
                id=uuid.uuid4(),
                poll=poll,
                text=opt.get('text', ''),
                order=i,
                vote_count=opt.get('votes', 0),
            )
            created_options.append(po)

        # Re-link each existing vote to the correct PollOption
        for vote in CommunityPollVote.objects.filter(poll=poll):
            idx = vote.option_index
            if idx is not None and 0 <= idx < len(created_options):
                vote.option = created_options[idx]
                vote.save(update_fields=['option'])


def migrate_options_reverse(apps, schema_editor):
    """Restore the JSONField from PollOption rows and option_index from option FK."""
    CommunityPoll = apps.get_model('lost_found', 'CommunityPoll')
    PollOption = apps.get_model('lost_found', 'PollOption')
    CommunityPollVote = apps.get_model('lost_found', 'CommunityPollVote')

    for poll in CommunityPoll.objects.all():
        options_list = list(
            PollOption.objects.filter(poll=poll)
            .order_by('order')
            .values('text', 'vote_count')
        )
        poll.options = [{'text': o['text'], 'votes': o['vote_count']} for o in options_list]
        poll.save(update_fields=['options'])

        index_map = {
            po.id: po.order
            for po in PollOption.objects.filter(poll=poll)
        }
        for vote in CommunityPollVote.objects.filter(poll=poll):
            if vote.option_id and vote.option_id in index_map:
                vote.option_index = index_map[vote.option_id]
                vote.save(update_fields=['option_index'])


class Migration(migrations.Migration):
    dependencies = [
        ('lost_found', '0003_poll_extended'),
    ]

    operations = [
        # 1. Create the PollOption table
        migrations.CreateModel(
            name='PollOption',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('poll', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='poll_options',
                    to='lost_found.communitypoll',
                )),
                ('text', models.CharField(max_length=200)),
                ('order', models.PositiveIntegerField(default=0)),
                ('vote_count', models.PositiveIntegerField(default=0)),
            ],
            options={
                'db_table': 'community_poll_options',
                'ordering': ['order'],
            },
        ),

        # 2. Add nullable option FK to CommunityPollVote
        migrations.AddField(
            model_name='communitypollvote',
            name='option',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='votes',
                to='lost_found.polloption',
            ),
        ),

        # 3. Data migration: JSONField → PollOption rows; option_index → option FK
        migrations.RunPython(migrate_options_forward, reverse_code=migrate_options_reverse),

        # 4. Make option FK required now that all rows are populated
        migrations.AlterField(
            model_name='communitypollvote',
            name='option',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='votes',
                to='lost_found.polloption',
            ),
        ),

        # 5. Drop the old option_index column
        migrations.RemoveField(
            model_name='communitypollvote',
            name='option_index',
        ),

        # 6. Drop the options JSONField from CommunityPoll
        migrations.RemoveField(
            model_name='communitypoll',
            name='options',
        ),

        # 7. Replace the old unnamed unique_together with a named UniqueConstraint
        migrations.AlterUniqueTogether(
            name='communitypollvote',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='communitypollvote',
            constraint=models.UniqueConstraint(
                fields=['poll', 'user'],
                name='one_vote_per_user_per_poll',
            ),
        ),
    ]

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('lost_found', '0004_poll_option_model'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add denormalized score column to community_questions
        migrations.AddField(
            model_name='communityquestion',
            name='score',
            field=models.IntegerField(default=0),
        ),

        # 2. Add covering index for TOP sort (score desc, then recency)
        migrations.AddIndex(
            model_name='communityquestion',
            index=models.Index(fields=['-score', '-created_at'], name='cq_score_created_idx'),
        ),

        # 3. Create community_question_votes table
        migrations.CreateModel(
            name='QuestionVote',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False, primary_key=True, serialize=False,
                )),
                ('question', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='votes',
                    to='lost_found.communityquestion',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='question_votes',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'community_question_votes',
            },
        ),

        # 4. Named unique constraint — same pattern as one_vote_per_user_per_poll
        migrations.AddConstraint(
            model_name='questionvote',
            constraint=models.UniqueConstraint(
                fields=['question', 'user'],
                name='one_vote_per_user_per_question',
            ),
        ),
    ]

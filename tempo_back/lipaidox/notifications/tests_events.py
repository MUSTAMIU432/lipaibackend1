"""
One-to-one notification events, follow requests and the mobile push switches.

    ./test.sh db lipaidox.notifications.tests_events

Device push is patched out (it is a background task); these check the rows,
the privacy rules and the preferences that gate them.
"""
from unittest import mock

from django.test import TestCase

from lipaidox.auth.models import User
from lipaidox.content.models import Content
from lipaidox.creator_profile.models import CreatorProfile, Follow, FollowRequest, FollowRequestStatus
from lipaidox.notifications.models.notification import Notification
from lipaidox.notifications.models.notification_preferences import NotificationPreference
from lipaidox.notifications.services import events



def make_user(name, role="viewer"):
    return User.objects.create_user(username=name, email=f"{name}@example.com", password="x", role=role)


class Ctx:
    """Minimal GraphQL `info` carrying a signed-in user."""

    def __init__(self, user):
        self.context = mock.Mock(request=mock.Mock(user=user))


class EventTests(TestCase):
    def setUp(self):
        patcher = mock.patch("lipaidox.tasking.enqueue_on_commit")
        self.queued = patcher.start()
        self.addCleanup(patcher.stop)
        self.owner = make_user("owner", "creator")
        self.fan = make_user("fan")
        profile = CreatorProfile.objects.create(user=self.owner, username="owner")
        self.content = Content.objects.create(creator=profile, title="Hello", status="published")

    def rows(self, ntype):
        return Notification.objects.filter(notification_type=ntype)

    def test_like_notifies_the_owner_once_and_queues_a_push(self):
        events.notify_like(self.content, self.fan)
        events.notify_like(self.content, self.fan)  # like → unlike → like
        (row,) = self.rows("new_like")
        self.assertEqual((row.user, row.sender, row.entity_id), (self.owner, self.fan, str(self.content.id)))
        self.queued.assert_called_once()

    def test_nobody_is_notified_about_their_own_action(self):
        self.assertIsNone(events.notify_like(self.content, self.owner))
        self.assertEqual(Notification.objects.count(), 0)

    def test_turning_a_switch_off_silences_that_type(self):
        NotificationPreference.bulk_update_preferences(self.owner, {"notify_new_like": False})
        self.assertIsNone(events.notify_like(self.content, self.fan))
        self.assertEqual(self.rows("new_like").count(), 0)

    def test_reply_tells_the_comment_author_as_well_as_the_post_owner(self):
        from lipaidox.content.models import ContentComment

        other = make_user("other")
        top = ContentComment.objects.create(author=other, content=self.content, body="first")
        reply = ContentComment.objects.create(author=self.fan, content=self.content, body="re", parent=top)
        events.notify_comment(self.content, reply, self.fan)
        self.assertEqual({n.user for n in self.rows("new_comment")}, {self.owner, other})

    def test_deliver_push_respects_the_master_switch_and_quiet_hours(self):
        n = events.notify_follow(self.fan, self.owner)
        with mock.patch("lipaidox.notifications.services.push.active_tokens_for_users", return_value=["tok"]), \
                mock.patch("lipaidox.notifications.services.push.send_push", return_value=1) as send:
            self.assertEqual(events.deliver_push(n), 1)
            send.assert_called_once()
            self.assertEqual(send.call_args.kwargs["data"]["type"], "new_follower")
            NotificationPreference.bulk_update_preferences(self.owner, {"push_enabled": False})
            self.assertEqual(events.deliver_push(n), 0)

    def test_follow_request_gets_accept_decline_buttons(self):
        n = events.notify_follow_request(self.fan, self.owner)
        with mock.patch("lipaidox.notifications.services.push.active_tokens_for_users", return_value=["tok"]), \
                mock.patch("lipaidox.notifications.services.push.send_push", return_value=1) as send:
            events.deliver_push(n)
        self.assertEqual(send.call_args.kwargs["category"], "follow_request")


class FollowRequestTests(TestCase):
    def setUp(self):
        patcher = mock.patch("lipaidox.tasking.enqueue_on_commit")
        patcher.start()
        self.addCleanup(patcher.stop)
        from lipaidox.creator_profile.mutations.profile_mutation import ProfileMutation
        from lipaidox.creator_profile.queries.profile_query import ProfileQuery

        self.m, self.q = ProfileMutation(), ProfileQuery()
        self.private = make_user("private")
        self.private.requires_follow_approval = True
        self.private.save()
        self.fan = make_user("fan")

    def test_public_account_follows_immediately_and_notifies(self):
        public = make_user("public")
        self.assertTrue(self.m.follow_user(Ctx(self.fan), str(public.id)))
        self.assertTrue(Follow.objects.filter(follower=self.fan, followed=public).exists())
        self.assertEqual(Notification.objects.filter(user=public, notification_type="new_follower").count(), 1)

    def test_private_account_only_records_a_request(self):
        self.assertFalse(self.m.follow_user(Ctx(self.fan), str(self.private.id)))
        self.assertFalse(Follow.objects.filter(follower=self.fan).exists())
        self.assertEqual(self.q.follow_state(Ctx(self.fan), str(self.private.id)), "requested")
        self.assertEqual(Notification.objects.filter(user=self.private, notification_type="new_follow_request").count(), 1)
        # Tapping again must not spam the owner.
        self.m.follow_user(Ctx(self.fan), str(self.private.id))
        self.assertEqual(Notification.objects.filter(user=self.private, notification_type="new_follow_request").count(), 1)

    def test_accept_creates_the_follow_and_tells_the_requester(self):
        self.m.follow_user(Ctx(self.fan), str(self.private.id))
        self.assertTrue(self.m.respond_to_follow_request(Ctx(self.private), str(self.fan.id), True))
        self.assertEqual(self.q.follow_state(Ctx(self.fan), str(self.private.id)), "following")
        self.assertEqual(Notification.objects.filter(user=self.fan, notification_type="follow_request_accepted").count(), 1)
        # Answering twice is a quiet no-op.
        self.assertFalse(self.m.respond_to_follow_request(Ctx(self.private), str(self.fan.id), True))

    def test_decline_keeps_the_requester_out_and_allows_one_more_ask(self):
        self.m.follow_user(Ctx(self.fan), str(self.private.id))
        self.m.respond_to_follow_request(Ctx(self.private), str(self.fan.id), False)
        self.assertEqual(self.q.follow_state(Ctx(self.fan), str(self.private.id)), "none")
        self.m.follow_user(Ctx(self.fan), str(self.private.id))
        self.assertEqual(FollowRequest.objects.get().status, FollowRequestStatus.PENDING)

    def test_only_the_target_can_answer(self):
        self.m.follow_user(Ctx(self.fan), str(self.private.id))
        stranger = make_user("stranger")
        self.assertFalse(self.m.respond_to_follow_request(Ctx(stranger), str(self.fan.id), True))
        self.assertFalse(Follow.objects.exists())

    def test_going_public_admits_everyone_waiting(self):
        self.m.follow_user(Ctx(self.fan), str(self.private.id))
        self.m.set_private_account(Ctx(self.private), False)
        self.assertTrue(Follow.objects.filter(follower=self.fan, followed=self.private).exists())


class PushPreferencesTests(TestCase):
    def test_only_the_fields_sent_change(self):
        from lipaidox.notifications.mutations.notification_mutation import NotificationMutation
        from lipaidox.notifications.queries.notification_query import NotificationQuery
        from lipaidox.notifications.schema.notification_schema import PushPreferencesInput

        user = make_user("prefs")
        before = NotificationQuery().my_push_preferences(Ctx(user))
        self.assertTrue(before.pushEnabled and before.newPosts and before.likes)
        after = NotificationMutation().update_push_preferences(
            Ctx(user), PushPreferencesInput(pushEnabled=False, likes=False)
        )
        self.assertFalse(after.pushEnabled)
        self.assertFalse(after.likes)
        self.assertTrue(after.newPosts and after.comments and after.follows)

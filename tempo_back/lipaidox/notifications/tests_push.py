"""Push routing: Expo tokens go to Expo, raw FCM tokens go to Firebase Admin. No DB, no network."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from lipaidox.notifications.services import push

EXPO = "ExponentPushToken[abc]"


class SendPushRoutingTests(SimpleTestCase):
    def test_tokens_are_split_by_shape(self):
        with mock.patch.object(push, "send_expo_push", return_value=1) as expo, \
                mock.patch.object(push, "send_fcm_push", return_value=2) as fcm:
            accepted = push.send_push([EXPO, "fcm-token-1", "fcm-token-2", EXPO], "t", "b", data={"k": "v"})
        self.assertEqual(accepted, 3)
        # Each sender filters to its own kind, so both get the full de-duplicated list.
        self.assertEqual(expo.call_args.args[0], [EXPO, "fcm-token-1", "fcm-token-2"])
        self.assertEqual(fcm.call_args.args[0], [EXPO, "fcm-token-1", "fcm-token-2"])


class SendFcmPushTests(SimpleTestCase):
    def _service(self, initialized=True):
        return mock.patch(
            "lipaidox.auth.googleOuth.googleOuth.FirebaseAuthService",
            return_value=SimpleNamespace(ensure_initialized=lambda: None, initialized=initialized),
        )

    def test_ignores_expo_tokens_and_empty_input(self):
        self.assertEqual(push.send_fcm_push([EXPO, "", None], "t", "b"), 0)

    def test_sends_data_only_message_expo_notifications_can_build_with_actions(self):
        import json

        from firebase_admin import messaging

        response = SimpleNamespace(success_count=2, responses=[SimpleNamespace(success=True)] * 2)
        with self._service(), mock.patch.object(messaging, "send_each_for_multicast", return_value=response) as send:
            accepted = push.send_fcm_push(
                ["a", "b", EXPO], "Title", "Body", data={"entityId": 7},
                image="https://x/y.jpg", category="post",
            )
        self.assertEqual(accepted, 2)
        message = send.call_args.args[0]
        self.assertEqual(message.tokens, ["a", "b"])
        # Data-only: a `notification` block would make Android draw it without action buttons.
        self.assertIsNone(message.notification)
        self.assertEqual(message.data["title"], "Title")
        self.assertEqual(message.data["message"], "Body")
        self.assertEqual(message.data["channelId"], push.ANDROID_CHANNEL_ID)
        self.assertEqual(message.data["categoryId"], "post")
        self.assertEqual(json.loads(message.data["body"]), {"entityId": 7, "image": "https://x/y.jpg"})

    def test_unregistered_tokens_are_deactivated(self):
        from firebase_admin import messaging

        dead = SimpleNamespace(success=False, exception=messaging.UnregisteredError("gone"))
        live = SimpleNamespace(success=True)
        response = SimpleNamespace(success_count=1, responses=[live, dead])
        with self._service(), \
                mock.patch.object(messaging, "send_each_for_multicast", return_value=response), \
                mock.patch.object(push, "_deactivate") as deactivate:
            self.assertEqual(push.send_fcm_push(["good", "stale"], "t", "b"), 1)
        deactivate.assert_called_once_with(["stale"])

    def test_skips_quietly_when_firebase_admin_is_not_ready(self):
        with self._service(initialized=False):
            self.assertEqual(push.send_fcm_push(["a"], "t", "b"), 0)

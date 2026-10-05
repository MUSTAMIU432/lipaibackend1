"""
Device push delivery.

The mobile app registers a push token via the ``registerPushToken`` mutation.
``send_push`` routes each token by shape:

* ``ExponentPushToken[...]`` goes to Expo's push service
  (https://exp.host/--/api/v2/push/send), which forwards to FCM/APNs.
* Anything else is a raw FCM registration token (what the app registers on
  Android since 1.3.0) and goes straight to Firebase Cloud Messaging through
  the Firebase Admin app the backend already initialises for Google sign-in,
  so no extra credential has to be uploaded anywhere.

We keep it dependency-free (stdlib ``urllib``) so no new package is needed on the
server, and we prune tokens Expo reports as ``DeviceNotRegistered`` so a stale
install stops receiving pushes. Delivery is best-effort: any failure is logged
and swallowed — a push that doesn't land must never break the write path that
triggered it (posting content, going live, sending a DM).
"""
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
# Expo accepts up to 100 messages per request.
_BATCH = 100


def _is_expo_token(token: str) -> bool:
    return bool(token) and token.startswith(("ExponentPushToken[", "ExpoPushToken["))


def send_expo_push(tokens, title, body, data=None, badge=None, sound="default", category=None):
    """
    Deliver one notification to many Expo push tokens.

    ``tokens`` is any iterable of token strings (non-Expo tokens are ignored).
    ``data`` is a small JSON-serialisable dict the app receives on tap — we use
    it to carry ``{type, url, entityId}`` for deep-linking. Returns the number of
    messages accepted by Expo. Never raises.
    """
    expo_tokens = [t for t in dict.fromkeys(tokens) if _is_expo_token(t)]
    if not expo_tokens:
        return 0

    accepted = 0
    for start in range(0, len(expo_tokens), _BATCH):
        chunk = expo_tokens[start:start + _BATCH]
        messages = []
        for tok in chunk:
            msg = {
                "to": tok,
                "title": title,
                "body": body,
                "sound": sound,
                "priority": "high",
            }
            if data is not None:
                msg["data"] = data
            if badge is not None:
                msg["badge"] = badge
            if category:
                msg["categoryId"] = category
            messages.append(msg)

        try:
            accepted += _post(messages, chunk)
        except Exception as exc:  # never let a push failure escape
            logger.warning("Expo push batch failed: %s", exc)
    return accepted


def _post(messages, chunk):
    payload = json.dumps(messages).encode("utf-8")
    req = urllib.request.Request(
        EXPO_PUSH_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
    body = json.loads(raw)
    tickets = body.get("data", []) if isinstance(body, dict) else []

    dead = []
    ok = 0
    for tok, ticket in zip(chunk, tickets):
        if not isinstance(ticket, dict):
            continue
        if ticket.get("status") == "ok":
            ok += 1
        else:
            details = ticket.get("details") or {}
            if details.get("error") == "DeviceNotRegistered":
                dead.append(tok)
    if dead:
        _deactivate(dead)
    return ok


def _deactivate(tokens):
    """Mark tokens Expo no longer recognises as inactive so we stop sending."""
    try:
        from lipaidox.notifications.models.push_tokens import PushToken
        PushToken.objects.filter(token__in=tokens).update(is_active=False)
    except Exception as exc:
        logger.warning("Failed to deactivate dead push tokens: %s", exc)


# Android notification channel the app creates on launch; must match
# ANDROID_CHANNEL_ID in the app's src/lib/push-notifications.ts.
ANDROID_CHANNEL_ID = "default"
_FCM_BATCH = 500


def send_fcm_push(tokens, title, body, data=None, image=None, category=None):
    """
    Deliver one notification to many raw FCM registration tokens through
    Firebase Admin. Returns the number accepted by FCM. Never raises; tokens FCM
    reports as unregistered are deactivated.

    Sent as a *data-only* message in the shape expo-notifications understands
    (``title`` / ``message`` / ``channelId`` / ``categoryId``, with ``body`` the
    JSON the app reads back as the notification's ``data``). A data-only message
    is built into the tray notification by the app's own code, which is the only
    way Android shows the action buttons its ``categoryId`` names (View Post /
    Dismiss, Accept / Decline). The cost: Android's system tray gets no cover
    image; the in-app pop-up still shows it. ``image`` rides along in ``body``.
    """
    tokens = list(dict.fromkeys(t for t in tokens if t and not _is_expo_token(t)))
    if not tokens:
        return 0
    try:
        from firebase_admin import messaging
        from lipaidox.auth.googleOuth.googleOuth import FirebaseAuthService

        service = FirebaseAuthService()
        service.ensure_initialized()
        if not service.initialized:
            logger.warning("FCM push skipped: Firebase Admin is not initialised.")
            return 0
    except Exception as exc:
        logger.warning("FCM push unavailable: %s", exc)
        return 0

    payload_data = dict(data or {})
    if image:
        payload_data["image"] = image
    payload = {
        "title": str(title),
        "message": str(body),
        "channelId": ANDROID_CHANNEL_ID,
        "color": "#006BFA",
        "body": json.dumps(payload_data, default=str),
    }
    if category:
        payload["categoryId"] = category

    accepted = 0
    dead = []
    for start in range(0, len(tokens), _FCM_BATCH):
        chunk = tokens[start:start + _FCM_BATCH]
        try:
            message = messaging.MulticastMessage(
                tokens=chunk,
                data=payload,
                android=messaging.AndroidConfig(priority="high"),
            )
            response = messaging.send_each_for_multicast(message)
        except Exception as exc:
            logger.warning("FCM batch failed: %s", exc)
            continue
        accepted += response.success_count
        for tok, result in zip(chunk, response.responses):
            if result.success:
                continue
            if isinstance(result.exception, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
                dead.append(tok)
            else:
                logger.warning("FCM send failed: %s", result.exception)
    if dead:
        _deactivate(dead)
    return accepted


def send_push(tokens, title, body, data=None, image=None, category=None):
    """Send to every token, Expo or FCM. Returns the number accepted. Never raises."""
    tokens = list(dict.fromkeys(tokens))
    return send_expo_push(tokens, title, body, data=data, category=category) + send_fcm_push(
        tokens, title, body, data=data, image=image, category=category
    )


def active_tokens_for_users(users):
    """Return active push token strings for an iterable of users."""
    from lipaidox.notifications.models.push_tokens import PushToken
    user_ids = [u.id for u in users]
    if not user_ids:
        return []
    return list(
        PushToken.objects.filter(user_id__in=user_ids, is_active=True)
        .values_list("token", flat=True)
    )

"""
Expo push delivery.

The mobile app registers an Expo push token (``ExponentPushToken[...]``) via the
``registerPushToken`` mutation; this module ships the notification to Expo's
push service (https://exp.host/--/api/v2/push/send), which forwards to FCM/APNs.

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


def send_expo_push(tokens, title, body, data=None, badge=None, sound="default"):
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

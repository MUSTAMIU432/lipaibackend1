"""The DM "sticker" catalog.

There's no sticker-pack image/CDN pipeline in this backend, so a sticker is an
oversized emoji rendered large by the client (`Message.sticker`) rather than an
uploaded image. Keeping the list here — server-side — means the client doesn't
hardcode its own copy that can drift from what `send_dm_message` accepts.
"""

STICKER_CATALOG = [
    "🎉", "❤️", "😂", "😍", "👍", "🔥", "🥳", "😢",
    "😮", "🙏", "👏", "💯", "🤝", "🎂", "😴", "🤔",
]

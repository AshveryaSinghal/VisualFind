"""
Turns the chat transcript the frontend sends (list of {role, content}) into
the `contents` array Gemini's API expects, and keeps it within a sane size.

This app has no server-side chat session store on purpose: the frontend
resends the full transcript with every turn (see AI SHOPPING ASSISTANT spec
- "Conversation Memory" here means the assistant faithfully sees the whole
conversation so far, not that the server persists it). That keeps the AI
router stateless and horizontally scalable, and matches how the rest of
this backend is built (no auth/session layer exists to hang server-side
state off of).
"""

from app.config import settings

VALID_ROLES = {"user", "assistant"}

class InvalidConversationError(Exception):
    pass

def build_gemini_contents(messages: list[dict]) -> list[dict]:
    """
    `messages` is the client-supplied transcript: [{"role": "user"|"assistant",
    "content": "..."}]. Returns Gemini's `contents` shape: role "assistant" is
    mapped to Gemini's "model" role. Trims to the most recent N turns so a
    very long conversation doesn't blow up the request payload.
    """
    if not messages:
        raise InvalidConversationError("messages must contain at least one entry")

    cleaned: list[dict] = []
    for msg in messages:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role not in VALID_ROLES:
            raise InvalidConversationError(f"Invalid role: {role!r}")
        if not content:
            continue
        cleaned.append({"role": role, "content": content})

    if not cleaned:
        raise InvalidConversationError("messages must contain at least one non-empty entry")

    max_turns = settings.ai_max_conversation_turns
    if len(cleaned) > max_turns:
        cleaned = cleaned[-max_turns:]

    return [
        {
            "role": "model" if m["role"] == "assistant" else "user",
            "parts": [{"text": m["content"]}],
        }
        for m in cleaned
    ]

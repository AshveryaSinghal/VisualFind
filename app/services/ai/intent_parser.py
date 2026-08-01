"""
Runs one Gemini chat turn (understand intent, ask a follow-up OR decide
we're ready to search) and validates the structured result.

Kept separate from gemini_service (transport) and conversation_manager
(transcript shaping) so this module's only job is: "is this Gemini reply a
well-formed chat-turn result, and if it says 'ready', does it actually carry
a usable search string?"
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import settings
from app.services import cache_service
from app.services.ai import conversation_manager, gemini_service
from app.services.ai.prompt_builder import CHAT_RESPONSE_SCHEMA, CHAT_SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)

@dataclass
class IntentResult:
    status: str
    assistant_message: str
    structured_query: dict = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"

def run_chat_turn(messages: list[dict], db: Session) -> IntentResult:
    """
    `messages`: full transcript as sent by the client, most recent message last.
    """
    contents = conversation_manager.build_gemini_contents(messages)

    cache_key = "ai_chat_turn:" + hashlib.sha256(
        json.dumps(contents, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cached = cache_service.get_cached(db, cache_key)
    if cached is not None:
        logger.info("AI Chat Turn | cache hit")
        return _from_dict(cached)

    raw = gemini_service.generate_json(
        system_instruction=CHAT_SYSTEM_INSTRUCTION,
        contents=contents,
        response_schema=CHAT_RESPONSE_SCHEMA,
        temperature=0.4,
    )
    result = _validate(raw)

    cache_service.set_cached(
        db,
        cache_key,
        {
            "status": result.status,
            "assistant_message": result.assistant_message,
            "structured_query": result.structured_query,
        },
        ttl_seconds=settings.gemini_chat_cache_ttl_seconds,
    )
    return result

def _validate(raw: dict) -> IntentResult:
    status = raw.get("status")
    if status not in ("collecting", "ready"):
        status = "collecting"

    assistant_message = (raw.get("assistant_message") or "").strip()
    if not assistant_message:
        assistant_message = (
            "Could you tell me a bit more about what you're looking for?"
        )

    structured_query = raw.get("structured_query") or {}
    if status == "ready" and not (structured_query.get("search_text") or "").strip():

        status = "collecting"

    return IntentResult(
        status=status,
        assistant_message=assistant_message,
        structured_query=structured_query if status == "ready" else {},
    )

def _from_dict(data: dict) -> IntentResult:
    return IntentResult(
        status=data.get("status", "collecting"),
        assistant_message=data.get("assistant_message", ""),
        structured_query=data.get("structured_query") or {},
    )

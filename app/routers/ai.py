"""
HTTP layer for the AI Shopping Assistant. Mirrors the shape of
app/routers/search.py: validate the request, call a service function,
translate the result (or a raised error) into an HTTP response. All Gemini
calls happen inside app/services/ai/* - nothing here talks to Gemini
directly.

This module is purely additive: it does not import from, modify, or change
the behavior of app/routers/search.py or the existing image-search
pipeline. Mounting it in app/main.py is a one-line addition.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import ComparedProduct, User, get_db
from app.deps import get_current_user
from app.models import (
    AIRecommendation,
    AISearchRequest,
    AISearchResponse,
    ChatTurnRequest,
    ChatTurnResponse,
    SmartCompareRequest,
    SmartCompareResponse,
    StructuredQuery,
    TextSearchRequest,
)
from app.rate_limit import DEFAULT_RATE_LIMIT, limiter
from app.services import text_search_service
from app.services.ai import (
    compare_engine,
    gemini_service,
    intent_parser,
    preference_extractor,
    recommendation_engine,
)
from app.services.ai.preference_extractor import ExtractedPreferences
from app.services.ai.conversation_manager import InvalidConversationError
from app.services.price_history_service import normalize_product_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai-shopping-assistant"])

def _handle_gemini_error(e: Exception):
    if isinstance(e, gemini_service.GeminiNotConfiguredError):
        raise HTTPException(status_code=503, detail=str(e))
    if isinstance(e, gemini_service.GeminiError):
        raise HTTPException(status_code=502, detail=str(e))
    logger.exception("Unexpected AI assistant failure")
    raise HTTPException(status_code=500, detail="AI assistant failed unexpectedly. Please try again.")

@router.post("/chat", response_model=ChatTurnResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
def chat_turn(
    request: Request,
    body: ChatTurnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    One turn of the conversational shopping assistant. The client sends the
    whole transcript so far (including the new user message); Gemini either
    asks a follow-up question or - once it has enough information - returns
    status="ready" plus a structured_query ready to hand to /api/ai/search.
    """
    try:
        messages = [{"role": m.role.value, "content": m.content} for m in body.messages]
        result = intent_parser.run_chat_turn(messages, db)
    except InvalidConversationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        _handle_gemini_error(e)
        raise

    structured_query = None
    if result.is_ready:
        prefs = preference_extractor.extract(result.structured_query)
        structured_query = StructuredQuery(
            category=prefs.category,
            budget_max=prefs.budget_max,
            budget_currency=prefs.budget_currency,
            brand=prefs.brand,
            preferences=prefs.preferences,
            search_text=prefs.search_text,
        )

    return ChatTurnResponse(
        status=result.status,
        assistant_message=result.assistant_message,
        structured_query=structured_query,
    )

def _ai_search_core(body: AISearchRequest, db: Session, user_id: int) -> AISearchResponse:
    """
    Shared implementation for /search and /text-search. Kept undecorated
    (no rate limiter here) so each public route below applies its own
    per-IP check instead of double-counting a single incoming HTTP request
    against the limiter.
    """
    query = body.search_text.strip()
    if not query:
        raise HTTPException(status_code=400, detail="search_text must not be empty")

    search_response = text_search_service.process_text_search(
        query, db, query_source="ai_chat", user_id=user_id
    )

    requirements_summary = ExtractedPreferences(
        category=body.category,
        budget_max=body.budget_max,
        budget_currency=body.budget_currency or "INR",
        brand=body.brand,
        preferences=body.preferences,
        search_text=query,
    ).as_requirements_summary()

    recommendation = None
    try:
        rec_result = recommendation_engine.recommend(
            search_response.results, requirements_summary, body.budget_max
        )
        if rec_result.recommended is not None:
            recommendation = AIRecommendation(
                product=rec_result.recommended,
                reason=rec_result.reason,
                why_it_matches=rec_result.why_it_matches,
                money_saved=rec_result.money_saved,
                is_official_store="official" in (rec_result.recommended.platform or "").lower(),
                alternatives=rec_result.alternatives,
                is_exact_match=search_response.is_exact_match,
                price_history=search_response.price_history,
            )
    except gemini_service.GeminiNotConfiguredError:

        logger.info("Gemini not configured - returning search results without a recommendation")

    return AISearchResponse(search=search_response, recommendation=recommendation)

@router.post("/search", response_model=AISearchResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
def ai_search(
    request: Request,
    body: AISearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AISearchResponse:
    """
    Runs the structured query (produced by /chat, or built by hand for a
    direct "describe what you need" flow) through the REAL search pipeline,
    then asks Gemini to rank the real results and recommend one. Never
    fabricates products - see app/services/ai/recommendation_engine.py.
    """
    return _ai_search_core(body, db, user_id=current_user.id)

@router.post("/text-search", response_model=AISearchResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
def text_search(
    request: Request,
    body: TextSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AISearchResponse:
    """
    Powers the Smart Search Bar's direct natural-language mode (no chat
    round-trip): the raw typed query is used as-is against the real search
    pipeline, then ranked the same way as the chat-driven flow.
    """
    return _ai_search_core(AISearchRequest(search_text=body.query), db, user_id=current_user.id)

@router.post("/compare-products", response_model=SmartCompareResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
def compare_products(
    request: Request,
    body: SmartCompareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SmartCompareResponse:
    """
    Powers the 'Compare Products' feature: the client sends two products it
    already has (from a real search response) plus a short preference
    questionnaire (budget, purpose, preferred brand, price-vs-quality
    priority, special preferences). Returns a personalized winner + charts
    data. Never re-runs a search or fabricates a product - see
    app/services/ai/compare_engine.py.

    Purely additive: does not touch /search, /text-search, or /chat above.
    """
    try:
        result = compare_engine.compare(body)
    except gemini_service.GeminiError as e:
        _handle_gemini_error(e)
        raise
    except Exception:
        logger.exception("Unexpected failure in compare-products")
        raise HTTPException(status_code=500, detail="Comparison failed unexpectedly. Please try again.")

    try:
        winner = body.product_a if result.winner_index == 0 else body.product_b
        db.add(
            ComparedProduct(
                user_id=current_user.id,
                product_a_name=body.product_a.title,
                product_a_key=normalize_product_key(body.product_a.title),
                product_b_name=body.product_b.title,
                product_b_key=normalize_product_key(body.product_b.title),
                winner_name=winner.title,
            )
        )
        db.commit()
    except Exception:
        logger.exception("Failed to log compared products for user_id=%s", current_user.id)
        db.rollback()

    return result

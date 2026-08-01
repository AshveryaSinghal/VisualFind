"""
HTTP layer only. All business logic lives in app/services/* - this router's
job is: validate the request, call a service function, translate the result
(or a raised error) into an HTTP response.
"""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SearchLog, User, get_db
from app.deps import get_current_user
from app.models import AnalyticsSummary, HistoryItem, PurchaseLink, SearchResponse, SortBy
from app.rate_limit import DEFAULT_RATE_LIMIT, limiter
from app.services import hybrid_search, search_service
from app.services.analytics_service import get_analytics_summary
from app.services.domain_filter import list_trusted_platforms
from app.services.price_utils import annotate_quick_commerce, apply_sort, pick_fastest_delivery
from app.services.search_providers import SearchProviderError
from app.services.serpapi_client import SerpApiError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

@router.post("/image", response_model=SearchResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def search_by_image(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    sort_by: SortBy | None = Query(None, description="Optional result ordering"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Use JPEG, PNG, or WebP.",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.2f} MB). Maximum allowed is {settings.max_upload_mb} MB.",
        )

    filename = file.filename or "upload.jpg"

    try:
        response = search_service.process_image_search(
            contents, filename, db, user_id=current_user.id, background_tasks=background_tasks
        )
    except (SearchProviderError, SerpApiError) as e:
        # SearchProviderError: the active search provider (Google Lens
        # today; whatever's configured via settings.search_provider
        # tomorrow) failed. SerpApiError can still surface directly from
        # the Google Shopping price-lookup tier (app/services/price_service.py),
        # which isn't part of the swappable provider surface. Either way,
        # from the client's perspective this is the same "an external
        # search backend failed" 502.
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        logger.exception("Unexpected failure while processing image search")
        raise HTTPException(status_code=500, detail="Image search failed unexpectedly. Please try again.")

    if sort_by is not None:
        response.results = apply_sort(response.results, sort_by.value)

    return response

@router.post("/hybrid", response_model=SearchResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def search_hybrid(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None, description="Product photo. Optional if text is provided."),
    text: str | None = Form(None, description="Free-text query, e.g. 'under 5000', 'white version', 'same but leather'."),
    sort_by: SortBy | None = Query(None, description="Optional result ordering"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    One endpoint for all three search modes - image only, text only, or
    both together - see app/services/hybrid_search/service.py for the
    actual routing/blending logic. `response.search_mode` tells the client
    which path answered the request ("image", "text", or "hybrid").
    """
    if not settings.enable_hybrid_search:
        raise HTTPException(status_code=503, detail="Hybrid search is currently disabled.")

    contents = None
    filename = None
    if file is not None:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Use JPEG, PNG, or WebP.",
            )
        contents = await file.read()
        size_mb = len(contents) / (1024 * 1024)
        if size_mb > settings.max_upload_mb:
            raise HTTPException(
                status_code=400,
                detail=f"File too large ({size_mb:.2f} MB). Maximum allowed is {settings.max_upload_mb} MB.",
            )
        filename = file.filename or "upload.jpg"

    try:
        response = hybrid_search.process_hybrid_search(
            db,
            image_bytes=contents,
            filename=filename,
            text_query=text,
            user_id=current_user.id,
            background_tasks=background_tasks,
        )
    except hybrid_search.InvalidHybridSearchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (SearchProviderError, SerpApiError) as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        logger.exception("Unexpected failure while processing hybrid search")
        raise HTTPException(status_code=500, detail="Search failed unexpectedly. Please try again.")

    if sort_by is not None:
        response.results = apply_sort(response.results, sort_by.value)

    return response

def _extract_thumbnail(log: SearchLog) -> str | None:
    """Pulls a representative product thumbnail out of a logged search's
    stored results - the best deal's image if there is one, otherwise the
    first result that has one. Defensive: malformed/missing results_json
    just means no thumbnail, never an error."""
    if not log.results_json:
        return None
    try:
        results = json.loads(log.results_json)
    except (TypeError, ValueError):
        return None
    if not results:
        return None

    best_deal = next((r for r in results if r.get("is_best_deal") and r.get("thumbnail")), None)
    if best_deal:
        return best_deal.get("thumbnail")

    return next((r.get("thumbnail") for r in results if r.get("thumbnail")), None)

@router.get("/history", response_model=list[HistoryItem])
def get_history(
    db: Session = Depends(get_db),
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):

    logs = (
        db.query(SearchLog)
        .filter(SearchLog.user_id == current_user.id)
        .order_by(SearchLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        HistoryItem(
            id=log.id,
            best_guess_label=log.best_guess_label,
            product_query=log.product_query,
            result_count=log.result_count,
            filtered_count=log.filtered_count,
            priced_count=log.priced_count or 0,
            best_deal_platform=log.best_deal_platform,
            best_deal_price=log.best_deal_price,
            detected_brand=log.detected_brand,
            brand_confidence=log.brand_confidence,
            official_domain=log.official_domain,
            execution_time_ms=log.execution_time_ms,
            created_at=log.created_at,
            thumbnail=_extract_thumbnail(log),
        )
        for log in logs
    ]

@router.get("/history/{search_id}", response_model=SearchResponse)
def get_search_detail(
    search_id: int,
    sort_by: SortBy | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    log = (
        db.query(SearchLog)
        .filter(SearchLog.id == search_id, SearchLog.user_id == current_user.id)
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Search not found")

    results = [PurchaseLink(**item) for item in json.loads(log.results_json or "[]")]
    results = annotate_quick_commerce(results)
    fastest_delivery = pick_fastest_delivery(results)
    if sort_by is not None:
        results = apply_sort(results, sort_by.value)

    return SearchResponse(
        search_id=log.id,
        best_guess_label=log.best_guess_label,
        product_query=log.product_query,
        total_matches_found=log.result_count,
        trusted_matches_returned=log.filtered_count,
        priced_count=log.priced_count or 0,
        detected_brand=log.detected_brand,
        brand_confidence=log.brand_confidence,
        official_domain=log.official_domain,
        official_product_found=bool(log.official_product_found),
        execution_time_ms=log.execution_time_ms,
        from_cache=False,
        results=results,
        note=None,
        fastest_delivery=fastest_delivery,
    )

@router.delete("/history/{search_id}", status_code=204)
def delete_history_item(
    search_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes a single search-history row belonging to the signed-in user."""
    log = (
        db.query(SearchLog)
        .filter(SearchLog.id == search_id, SearchLog.user_id == current_user.id)
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Search not found")
    db.delete(log)
    db.commit()
    return None

@router.delete("/history", status_code=204)
def clear_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes every search-history row belonging to the signed-in user only."""
    db.query(SearchLog).filter(SearchLog.user_id == current_user.id).delete()
    db.commit()
    return None

@router.get("/analytics/summary", response_model=AnalyticsSummary)
def get_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_analytics_summary(db, user_id=current_user.id)

@router.get("/platforms", response_model=list[str])
def get_platforms():
    """Exposes the trusted-platform allowlist. Adding a new platform is a
    one-line change in app/services/domain_filter.py - nothing else changes."""
    return list_trusted_platforms()

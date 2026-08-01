"""
HTTP layer for the internal Product Index - all real logic lives in
app/services/product_index/service.py, this just validates requests and
translates results into responses (same convention as the other routers).

Read endpoints require auth (same as the rest of the API) but are not
scoped to the current user - the Product Index is a shared catalog, not
per-user data.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import User, get_db
from app.deps import get_current_user
from app.models import (
    BackfillEmbeddingsResponse,
    BatchIndexRequest,
    IndexHealthHistoryItem,
    IndexHealthResponse,
    IndexingJobResponse,
    IndexStatsResponse,
    IndexVersionResponse,
    ProductIndexItem,
    ProductIndexListResponse,
    ProductIndexStatsResponse,
    RebuildIndexRequest,
    SearchLatencyMetricsResponse,
    SimilarProductItem,
    SimilarProductsResponse,
    VectorIndexStatsResponse,
)
from app.services.index_dashboard_service import get_index_dashboard_stats
from app.services.index_health_service import list_health_history, run_health_check
from app.services.indexing import jobs as indexing_jobs
from app.services.indexing import sources as indexing_sources
from app.services.indexing import versioning as indexing_versioning
from app.services.indexing.runner import run_api_pull_job, run_batch_job, run_rebuild_job
from app.services.indexing.types import RawProduct, SourceType
from app.services.product_index import service as index_service
from app.services.product_index.vector_index import default_vector_index_registry
from app.services.search_metrics_service import get_search_latency_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/product-index", tags=["product-index"])

def _job_to_response(job) -> IndexingJobResponse:
    return IndexingJobResponse.model_validate(job)

@router.post("/index/batch", response_model=IndexingJobResponse, status_code=202)
def index_batch(
    payload: BatchIndexRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IndexingJobResponse:
    """Batch-index products supplied directly (a caller-fetched partner
    API response, a manual admin import, ...) or pulled server-side from
    `api_url`. Runs asynchronously: this returns immediately with a
    queued job; poll GET /index/jobs/{id} for progress and results.
    """
    if not payload.products and not payload.api_url:
        raise HTTPException(status_code=400, detail="Provide either `products` or `api_url`.")
    if payload.products and payload.api_url:
        raise HTTPException(status_code=400, detail="Provide only one of `products` or `api_url`, not both.")

    if payload.api_url:
        job = indexing_jobs.create_job(
            db, source_type=SourceType.API, source_label=payload.source_label or payload.api_url, total=0
        )
        background_tasks.add_task(run_api_pull_job, job.id, payload.api_url, payload.source_label)
        return _job_to_response(job)

    raw_products = [
        RawProduct(
            title=item.title,
            brand=item.brand,
            category=item.category,
            image_url=item.image_url,
            description=item.description,
            price=item.price,
            currency=item.currency,
            rating=item.rating,
            review_count=item.review_count,
            source=item.source,
            product_url=item.product_url,
            external_id=item.external_id,
            raw=item.model_dump(),
        )
        for item in payload.products
    ]
    job = indexing_jobs.create_job(
        db, source_type=SourceType.API, source_label=payload.source_label, total=len(raw_products)
    )
    background_tasks.add_task(run_batch_job, job.id, raw_products, SourceType.API)
    return _job_to_response(job)

@router.post("/index/csv", response_model=IndexingJobResponse, status_code=202)
async def index_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_label: str | None = Query(None, description="Defaults to source column values, or the filename"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IndexingJobResponse:
    """Batch-index products from an uploaded CSV. Column names are matched
    loosely (title/name/product_name, image/image_url/thumbnail, etc - see
    app/services/indexing/sources.py::_FIELD_ALIASES); unrecognized
    columns are ignored. Runs asynchronously, same as /index/batch."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    content = await file.read()
    try:
        raw_products = indexing_sources.from_csv_bytes(
            content, default_source=source_label or file.filename
        )
    except Exception:
        logger.exception("Failed to parse uploaded CSV %s", file.filename)
        raise HTTPException(status_code=400, detail="Could not parse the uploaded CSV file.")

    if not raw_products:
        raise HTTPException(status_code=400, detail="No product rows found in the uploaded CSV.")

    job = indexing_jobs.create_job(
        db, source_type=SourceType.CSV, source_label=source_label or file.filename, total=len(raw_products)
    )
    background_tasks.add_task(run_batch_job, job.id, raw_products, SourceType.CSV)
    return _job_to_response(job)

@router.get("/index/jobs", response_model=list[IndexingJobResponse])
def list_indexing_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[IndexingJobResponse]:
    return [_job_to_response(job) for job in indexing_jobs.list_jobs(db, limit=limit)]

@router.get("/index/jobs/{job_id}", response_model=IndexingJobResponse)
def get_indexing_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IndexingJobResponse:
    job = indexing_jobs.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Indexing job not found")
    return _job_to_response(job)

@router.post("/index/rebuild", response_model=IndexingJobResponse, status_code=202)
def rebuild_index(
    payload: RebuildIndexRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IndexingJobResponse:
    """Kicks off a full Product Index rebuild: re-normalizes every catalog
    row and (by default) recomputes every embedding, regardless of whether
    it already has a current one. Use this after swapping
    `settings.product_index_embedding_backend`, after a normalization fix,
    or as a periodic full refresh - see app/services/indexing/rebuild.py.

    Runs asynchronously, same as CSV/API batch indexing: this returns
    immediately with a queued job. Poll GET /index/jobs/{id} for progress,
    or GET /index/versions/{id} for the resulting index version.
    """
    version = indexing_versioning.start_version(
        db,
        label=payload.label,
        triggered_by="api",
        notes="Created ahead of background rebuild; see linked indexing job.",
    )
    job = indexing_jobs.create_job(
        db,
        source_type=SourceType.REBUILD,
        source_label=payload.label or "Full Index Rebuild",
        total=0,
        index_version_id=version.id,
    )
    background_tasks.add_task(
        run_rebuild_job,
        job.id,
        version_id=version.id,
        full_reembed=payload.full_reembed,
        renormalize=payload.renormalize,
        max_embeddings=payload.max_embeddings,
        label=payload.label,
    )
    return _job_to_response(job)

@router.get("/index/versions", response_model=list[IndexVersionResponse])
def list_index_versions(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[IndexVersionResponse]:
    return [IndexVersionResponse.model_validate(v) for v in indexing_versioning.list_versions(db, limit=limit)]

@router.get("/index/versions/active", response_model=IndexVersionResponse)
def get_active_index_version(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IndexVersionResponse:
    version = indexing_versioning.get_active_version(db)
    if version is None:
        raise HTTPException(status_code=404, detail="No index version has been activated yet.")
    return IndexVersionResponse.model_validate(version)

@router.get("/index/versions/{version_id}", response_model=IndexVersionResponse)
def get_index_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IndexVersionResponse:
    version = indexing_versioning.get_version(db, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Index version not found")
    return IndexVersionResponse.model_validate(version)

@router.get("/health", response_model=IndexHealthResponse)
def get_index_health(
    persist: bool = Query(True, description="Store this result in the health-history table."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IndexHealthResponse:
    """Runs the Index Health Monitor: embedding coverage, stale embeddings
    (after a backend swap), active-version freshness, recent indexing-job
    failure rate, and recent search latency, rolled up into one overall
    healthy/degraded/unhealthy status. See app/services/index_health_service.py.
    """
    return IndexHealthResponse(**run_health_check(db, persist=persist))

@router.get("/health/history", response_model=list[IndexHealthHistoryItem])
def get_index_health_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[IndexHealthHistoryItem]:
    return [IndexHealthHistoryItem(**snapshot) for snapshot in list_health_history(db, limit=limit)]

@router.get("/metrics/search-latency", response_model=SearchLatencyMetricsResponse)
def get_search_latency(
    window_minutes: int | None = Query(None, ge=1, le=10080, description="Restrict to the last N minutes."),
    limit: int = Query(5000, ge=1, le=20000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchLatencyMetricsResponse:
    """p50/p95/p99 search latency and a breakdown by query_source (internal
    index, Google Lens fallback, cache, hybrid/text search, ...), computed
    from search history. See app/services/search_metrics_service.py.
    """
    return SearchLatencyMetricsResponse(**get_search_latency_metrics(db, window_minutes=window_minutes, limit=limit))

@router.get("", response_model=ProductIndexListResponse)
def list_products(
    q: str | None = Query(None, description="Substring match against product title"),
    category: str | None = Query(None),
    brand: str | None = Query(None),
    source: str | None = Query(None, description="Marketplace, e.g. Amazon"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductIndexListResponse:
    rows, total = index_service.list_entries(
        db, query=q, category=category, brand=brand, source=source, limit=limit, offset=offset
    )
    return ProductIndexListResponse(
        items=[index_service.to_item(row) for row in rows], total=total, limit=limit, offset=offset
    )

@router.get("/stats", response_model=ProductIndexStatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductIndexStatsResponse:
    return ProductIndexStatsResponse(**index_service.get_stats(db))

@router.get("/stats/dashboard", response_model=IndexStatsResponse)
def get_stats_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IndexStatsResponse:
    """Everything the Index Statistics dashboard needs in one call: catalog
    size/coverage, embedding backfill progress, duplicate-detection totals
    from the indexing pipeline's job history, and search-time metrics
    (latency, cache hit rate, internal-index vs Google-Lens-fallback usage,
    top searched products/brands). See app/services/index_dashboard_service.py.
    """
    return get_index_dashboard_stats(db)

@router.post("/backfill-embeddings", response_model=BackfillEmbeddingsResponse)
def backfill_embeddings(
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BackfillEmbeddingsResponse:
    """Manually kicks off embedding computation for catalog rows that don't
    have one yet. Not on any schedule in this phase - call it (e.g. from an
    admin action or a cron hitting this endpoint) to catch the catalog up."""
    updated = index_service.backfill_embeddings(db, limit=limit)
    return BackfillEmbeddingsResponse(updated=updated)

@router.get("/vector-index/stats", response_model=VectorIndexStatsResponse)
def get_vector_index_stats(
    current_user: User = Depends(get_current_user),
) -> VectorIndexStatsResponse:
    """Introspection into the in-memory FAISS index itself (vector counts
    per embedding dimension) - see app/services/product_index/vector_index.py.
    Note this reflects whatever has been reconciled into the index by
    searches so far in this process, not necessarily the full catalog -
    call a search (or POST /backfill-embeddings) first if this looks lower
    than ProductIndexStatsResponse.products_with_embeddings."""
    return VectorIndexStatsResponse(**default_vector_index_registry.stats())

@router.post("/vector-index/persist", status_code=202)
def persist_vector_index(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Manually flushes the FAISS index to
    `settings.product_index_faiss_dir`. Normally handled automatically on
    app shutdown (see app/main.py) - this is for operators who want a
    persisted snapshot without restarting the process, e.g. before a
    planned deploy."""
    from app.config import settings

    default_vector_index_registry.save(settings.product_index_faiss_dir)
    return {"status": "persisted", "directory": settings.product_index_faiss_dir}

@router.get("/{product_id}", response_model=ProductIndexItem)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductIndexItem:
    entry = index_service.get_entry(db, product_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Product not found in index")
    return index_service.to_item(entry)

@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Removes a catalog row entirely, including its vector from the
    internal FAISS nearest-neighbor index (see
    app/services/product_index/vector_index.py) if it had one. This is a
    hard delete - there's no soft-delete/undo here, same as the rest of
    the Product Index's admin surface."""
    deleted = index_service.delete_entry(db, product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found in index")

@router.get("/{product_id}/similar", response_model=SimilarProductsResponse)
def get_similar_products(
    product_id: int,
    top_k: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SimilarProductsResponse:
    """Visual-similarity search *within VisualFind's own catalog* - the
    core building block of true multimodal product search, as opposed to
    the current Google-Lens-only pipeline."""
    entry = index_service.get_entry(db, product_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Product not found in index")
    if not entry.embedding_json:
        raise HTTPException(
            status_code=409,
            detail=(
                "This product doesn't have an embedding yet. Trigger "
                "POST /api/product-index/backfill-embeddings and try again."
            ),
        )

    ranked = index_service.rank_similar(db, product_id, top_k=top_k, user_id=current_user.id)
    items = []
    for result in ranked:
        visual_similarity = next(
            (c.raw_score for c in result.score.contributions if c.name == "visual_similarity"),
            None,
        )
        items.append(
            SimilarProductItem(
                product=index_service.to_item(result.candidate),
                similarity=round(visual_similarity or 0.0, 4),
                ranking_score=result.score.total_score,
                ranking_explanation=[
                    index_service.to_ranking_contribution_schema(c) for c in result.score.contributions
                ],
                ranking_summary=result.score.summary,
            )
        )
    return SimilarProductsResponse(product_id=product_id, items=items)

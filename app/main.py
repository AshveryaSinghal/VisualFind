from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.rate_limit import limiter
from app.logging_config import configure_logging
from app.database import init_db
from app.routers import ai, auth, personalization, products, search
from app.services.product_index.vector_index import default_vector_index_registry

configure_logging()

app = FastAPI(
    title="VisualFind API",
    description="Upload a product photo, get purchase links from trusted e-commerce platforms.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down and try again shortly."},
    )

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(ai.router)
app.include_router(products.router)
app.include_router(personalization.router)
# product_index.router intentionally not registered: the internal Product
# Index (image similarity matching) was disabled - see
# settings.enable_product_index's comment in app/config.py - because it
# could return the wrong brand's product for a visually-similar item. Its
# stats/dashboard/health endpoints are removed along with it. The
# underlying module is left in place, not deleted, so it can be re-enabled
# behind a real vision-model backend later without rebuilding it from
# scratch.

@app.on_event("startup")
def on_startup():
    init_db()
    if settings.product_index_faiss_persist_enabled:
        default_vector_index_registry.load(settings.product_index_faiss_dir)

@app.on_event("shutdown")
def on_shutdown():
    if settings.product_index_faiss_persist_enabled:
        default_vector_index_registry.save(settings.product_index_faiss_dir)

@app.get("/")
def root():
    return {"status": "ok", "service": "VisualFind API"}

@app.get("/health")
def health():
    return {"status": "healthy"}

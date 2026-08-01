"""
The Indexing Pipeline: the one place that turns "a product was discovered
somewhere" (a Google Lens result, a row of a supplier CSV, a record from a
partner API) into a row in VisualFind's internal Product Index.

See pipeline.py for the orchestration and the module docstring there for
the full stage breakdown (normalize -> dedupe -> store -> embed -> update
indexes).
"""

from app.services.indexing.pipeline import IndexingPipeline, default_pipeline
from app.services.indexing.types import IndexingResult, RawProduct, SourceType

__all__ = [
    "IndexingPipeline",
    "default_pipeline",
    "IndexingResult",
    "RawProduct",
    "SourceType",
]

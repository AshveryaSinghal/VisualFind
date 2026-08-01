"""
Multi-stage price extraction pipeline.

Public entry point: PriceExtractionService.extract(candidate, offers_by_platform)
-> ExtractionResult(price, currency, price_source, extraction_method, confidence_score).

See service.py for the full tier-by-tier breakdown.
"""

from app.services.price_extraction.service import PriceExtractionService
from app.services.price_extraction.types import ExtractionResult, PriceCandidate, PriceRole

__all__ = ["PriceExtractionService", "ExtractionResult", "PriceCandidate", "PriceRole"]

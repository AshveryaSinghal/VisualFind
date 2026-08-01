"""
Brand Resolution engine.

Public entry point: BrandResolutionService.resolve(lens_response, candidates, query)
-> BrandResolutionResult(detected_brand, brand_confidence, official_domain,
                          official_product, ...).

Kept entirely separate from app/services/search_service.py and
app/services/domain_filter.py - search_service makes exactly one call into
this package and merges the (optional) official product into its existing
result list; no brand-specific logic lives outside this package. See
service.py for the full pipeline breakdown.
"""

from app.services.brand_resolution.service import BrandResolutionService, official_product_to_merge_dict
from app.services.brand_resolution.types import BrandResolutionResult, OfficialProduct

__all__ = [
    "BrandResolutionService",
    "BrandResolutionResult",
    "OfficialProduct",
    "official_product_to_merge_dict",
]

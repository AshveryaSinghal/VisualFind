"""
Hybrid Search - image only, text only, or image + text, through one
entry point. See service.py::process_hybrid_search for the orchestration
and query_parser.py for how a typed query becomes a budget constraint plus
free text.
"""

from .query_parser import ParsedTextQuery, parse_hybrid_text
from .service import InvalidHybridSearchError, process_hybrid_search

__all__ = [
    "ParsedTextQuery",
    "parse_hybrid_text",
    "InvalidHybridSearchError",
    "process_hybrid_search",
]

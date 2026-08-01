"""
Index Rebuild command.

Usage:
    python -m app.scripts.rebuild_index
    python -m app.scripts.rebuild_index --catch-up          # only fill in missing/stale embeddings
    python -m app.scripts.rebuild_index --no-renormalize
    python -m app.scripts.rebuild_index --max-embeddings 500
    python -m app.scripts.rebuild_index --label "post backend swap"

Runs the same app/services/indexing/rebuild.py::rebuild_index() logic the
POST /api/product-index/index/rebuild endpoint schedules in the
background, but synchronously and from the command line - for an operator
who wants to run it directly (a deploy step, a cron entry, a one-off after
changing settings.product_index_embedding_backend) without needing the API
server up or an auth token.

Exits non-zero if the rebuild fails, so it's safe to use as a CI/cron step
whose exit code is checked.
"""

from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal, init_db
from app.services.indexing.rebuild import rebuild_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild VisualFind's Product Index.")
    parser.add_argument(
        "--catch-up",
        action="store_true",
        help="Only (re)embed products missing an embedding or stamped with a stale backend, "
        "instead of forcing every embedding to recompute.",
    )
    parser.add_argument("--no-renormalize", action="store_true", help="Skip re-running title/brand normalization.")
    parser.add_argument("--max-embeddings", type=int, default=None, help="Cap on how many embeddings to (re)compute.")
    parser.add_argument("--label", type=str, default=None, help="Human-readable label for the resulting index version.")
    args = parser.parse_args(argv)

    init_db()
    db = SessionLocal()
    try:
        result = rebuild_index(
            db,
            full_reembed=not args.catch_up,
            renormalize=not args.no_renormalize,
            max_embeddings=args.max_embeddings,
            label=args.label,
            triggered_by="cli",
        )
    finally:
        db.close()

    print(f"Index Rebuild {'succeeded' if result.status == 'active' else 'FAILED'}")
    print(f"  version:          #{result.version_number}")
    print(f"  total entries:    {result.total_entries}")
    print(f"  renormalized:     {result.renormalized}")
    print(f"  re-embedded:      {result.re_embedded}")
    print(f"  embedding failed: {result.embedding_failed}")
    if result.errors:
        print(f"  errors ({len(result.errors)}):")
        for error in result.errors[:20]:
            print(f"    - {error}")

    return 0 if result.status == "active" else 1


if __name__ == "__main__":
    sys.exit(main())

"""
Lightweight analytics computed straight from search_logs - no new
infrastructure, just aggregation queries over data we're already storing per
search (see app/database.py: SearchLog).
"""

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.database import SearchLog
from app.models import AnalyticsSummary

_TOP_N = 10
_TREND_DAYS = 7

def _top_n(counter: Counter, n: int = _TOP_N) -> list[dict]:
    return [{"name": name, "count": count} for name, count in counter.most_common(n) if name]

def get_analytics_summary(db: Session, user_id: int | None = None) -> AnalyticsSummary:
    query = db.query(SearchLog)
    if user_id is not None:

        query = query.filter(SearchLog.user_id == user_id)
    logs = query.all()

    if not logs:
        return AnalyticsSummary(
            total_searches=0,
            most_searched_products=[],
            most_searched_platforms=[],
            most_searched_brands=[],
            average_search_time_ms=None,
            average_products_found=None,
            average_priced_products=None,
            total_products_found=0,
            price_hit_rate=None,
            official_match_rate=None,
            fastest_search_ms=None,
            searches_last_7_days=0,
            searches_by_day=[],
            best_deal_found=None,
            last_search_at=None,
        )

    product_counter = Counter((log.product_query or "").strip().lower() for log in logs if log.product_query)
    platform_counter = Counter(log.best_deal_platform for log in logs if log.best_deal_platform)

    brand_counter = Counter(
        (log.product_query or "").strip().lower().split()[0]
        for log in logs
        if log.product_query and log.product_query.strip()
    )

    exec_times = [log.execution_time_ms for log in logs if log.execution_time_ms is not None]
    result_counts = [log.result_count for log in logs if log.result_count is not None]
    priced_counts = [log.priced_count for log in logs if log.priced_count is not None]

    total_searches = len(logs)
    total_products_found = sum(result_counts) if result_counts else 0

    searches_with_a_price = sum(1 for log in logs if (log.priced_count or 0) > 0)
    price_hit_rate = round((searches_with_a_price / total_searches) * 100, 1) if total_searches else None

    official_matches = sum(1 for log in logs if log.official_product_found)
    official_match_rate = round((official_matches / total_searches) * 100, 1) if total_searches else None

    fastest_search_ms = min(exec_times) if exec_times else None

    now = datetime.utcnow()
    window_start = now - timedelta(days=_TREND_DAYS - 1)
    day_buckets: dict[str, int] = {
        (window_start + timedelta(days=offset)).strftime("%Y-%m-%d"): 0 for offset in range(_TREND_DAYS)
    }
    searches_last_7_days = 0
    for log in logs:
        if not log.created_at:
            continue
        day_key = log.created_at.strftime("%Y-%m-%d")
        if day_key in day_buckets:
            day_buckets[day_key] += 1
            searches_last_7_days += 1

    searches_by_day = [{"date": day, "count": count} for day, count in day_buckets.items()]

    priced_deals = [log for log in logs if log.best_deal_price is not None]
    best_deal_log = min(priced_deals, key=lambda log: log.best_deal_price) if priced_deals else None
    best_deal_found = (
        {
            "label": best_deal_log.best_guess_label or best_deal_log.product_query or "Product",
            "platform": best_deal_log.best_deal_platform,
            "price": best_deal_log.best_deal_price,
            "search_id": best_deal_log.id,
        }
        if best_deal_log
        else None
    )

    last_search_at = max((log.created_at for log in logs if log.created_at), default=None)

    return AnalyticsSummary(
        total_searches=total_searches,
        most_searched_products=_top_n(product_counter),
        most_searched_platforms=_top_n(platform_counter),
        most_searched_brands=_top_n(brand_counter),
        average_search_time_ms=round(sum(exec_times) / len(exec_times), 1) if exec_times else None,
        average_products_found=round(sum(result_counts) / len(result_counts), 2) if result_counts else None,
        average_priced_products=round(sum(priced_counts) / len(priced_counts), 2) if priced_counts else None,
        total_products_found=total_products_found,
        price_hit_rate=price_hit_rate,
        official_match_rate=official_match_rate,
        fastest_search_ms=fastest_search_ms,
        searches_last_7_days=searches_last_7_days,
        searches_by_day=searches_by_day,
        best_deal_found=best_deal_found,
        last_search_at=last_search_at.isoformat() if last_search_at else None,
    )

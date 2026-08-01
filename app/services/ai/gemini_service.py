"""
Thin wrapper around Google's Gemini `generateContent` REST endpoint.

This module knows nothing about shopping, chat turns, or products - it only
knows how to send (system instruction + conversation contents + optional
JSON schema) and get back either free text or a parsed JSON object. Every
other AI module builds on top of this one.

Docs: https://ai.google.dev/api/generate-content

Kept dependency-free (plain `requests`, already used elsewhere in this
codebase for SerpApi) rather than pulling in the google-generativeai SDK.
"""

import json
import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

class GeminiError(Exception):
    """Raised for any failure talking to Gemini - network, auth, quota, or a
    malformed response. Callers should catch this and degrade gracefully
    (e.g. surface a friendly chat error) rather than 500ing the request."""

class GeminiNotConfiguredError(GeminiError):
    """Raised when GEMINI_API_KEY is empty. Distinct from GeminiError so
    the router can return a clear 503 'AI assistant is not configured'
    instead of a generic failure."""

def _require_api_key() -> str:
    if not settings.gemini_api_key:
        raise GeminiNotConfiguredError(
            "GEMINI_API_KEY is not set. Add it to your .env to enable the AI Shopping Assistant."
        )
    return settings.gemini_api_key

def generate_json(
    system_instruction: str,
    contents: list[dict],
    response_schema: dict,
    temperature: float = 0.4,
) -> dict:
    """
    Calls Gemini and returns a parsed JSON object constrained to
    `response_schema` (Gemini's structured-output mode). This is what the
    intent parser and recommendation engine use - it guarantees the shape
    of what comes back instead of hoping the model formats free text
    correctly.
    """
    raw_text = _call_gemini(
        system_instruction=system_instruction,
        contents=contents,
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=response_schema,
    )
    try:
        return json.loads(raw_text)
    except (TypeError, ValueError) as e:
        raise GeminiError(f"Gemini returned malformed JSON: {e}") from e

def _extract_error_detail(resp: requests.Response) -> str:
    """
    Google's 429 body includes a `status` (e.g. RESOURCE_EXHAUSTED) and, in
    `details`, a `QuotaFailure` naming exactly which quota was hit.
    `quotaId` (e.g. "GenerateRequestsPerDayPerProjectPerModel-FreeTier") is
    the useful field - it says whether this is a per-minute or per-day cap.
    `quotaMetric` is just the API method name and is the same for both, so
    it's kept only as a fallback. A `RetryInfo` detail, when present, gives
    the exact number of seconds Google wants you to wait before retrying.
    """
    try:
        body = resp.json()
        error = body.get("error", {})
        status = error.get("status", "UNKNOWN")

        violations = []
        retry_delay = None
        for d in error.get("details", []):
            detail_type = d.get("@type", "")
            if "QuotaFailure" in detail_type:
                for v in d.get("violations", []):
                    limit = v.get("quotaId") or v.get("quotaMetric")
                    if limit and limit not in violations:
                        violations.append(limit)
            elif "RetryInfo" in detail_type:
                retry_delay = d.get("retryDelay")

        parts = [status]
        if violations:
            parts.append(", ".join(violations))
        if retry_delay:
            parts.append(f"retry after {retry_delay}")
        return " | ".join(parts) if len(parts) > 1 else parts[0]
    except (ValueError, AttributeError):
        return resp.text[:200] if resp.text else "no detail in response"

def _call_gemini(
    system_instruction: str,
    contents: list[dict],
    temperature: float,
    response_mime_type: str | None = None,
    response_schema: dict | None = None,
) -> str:
    api_key = _require_api_key()
    url = GEMINI_ENDPOINT_TEMPLATE.format(model=settings.gemini_model)

    generation_config: dict = {"temperature": temperature}
    if response_mime_type:
        generation_config["response_mime_type"] = response_mime_type
    if response_schema:
        generation_config["response_schema"] = response_schema

    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": contents,
        "generationConfig": generation_config,
    }

    try:
        resp = requests.post(
            url,
            params={"key": api_key},
            json=payload,
            timeout=settings.gemini_timeout_seconds,
        )
    except requests.RequestException as e:
        raise GeminiError(f"Network error calling Gemini: {e}") from e

    if resp.status_code == 401 or resp.status_code == 403:
        raise GeminiError("Gemini rejected the API key. Check GEMINI_API_KEY in .env.")
    if resp.status_code == 429:
        detail = _extract_error_detail(resp)
        logger.warning("Gemini 429 raw body: %s", resp.text[:1000])
        raise GeminiError(f"Gemini quota/rate limit exceeded ({detail}). Try again shortly.")
    if resp.status_code != 200:
        if resp.status_code == 404:
            raise GeminiError(
                f"Gemini model '{settings.gemini_model}' isn't available (HTTP 404). "
                "Google deprecates model names often - run "
                "`curl \"https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY\"` "
                "and set GEMINI_MODEL in .env to a current model that supports generateContent. "
                f"Raw error: {resp.text[:300]}"
            )
        raise GeminiError(f"Gemini returned HTTP {resp.status_code}: {resp.text[:400]}")

    data = resp.json()

    candidates = data.get("candidates") or []
    if not candidates:
        block_reason = (data.get("promptFeedback") or {}).get("blockReason")
        if block_reason:
            raise GeminiError(f"Gemini declined to respond (reason: {block_reason}).")
        raise GeminiError("Gemini returned no candidates.")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts)
    if not text:
        raise GeminiError("Gemini returned an empty response.")

    return text

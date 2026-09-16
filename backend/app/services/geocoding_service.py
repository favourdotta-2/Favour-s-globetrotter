import math
import threading
from collections import OrderedDict
from time import monotonic

import httpx
from fastapi import HTTPException

from app.core.config import Settings
from app.repositories.json_store import Record

CACHE_TTL_SECONDS = 86_400
CACHE_CAPACITY = 256
_cache: OrderedDict[tuple[str, str], tuple[float, list[Record]]] = OrderedDict()
_lock = threading.Lock()
_next_request_at = 0.0


def _parse_results(payload: object) -> list[Record]:
    if not isinstance(payload, list):
        raise HTTPException(502, "Place search returned an invalid response.")
    results: list[Record] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("address"), dict):
            raise HTTPException(502, "Place search returned an invalid address.")
        country = item["address"].get("country_code")
        if not isinstance(country, str):
            raise HTTPException(502, "Place search did not identify the result's country.")
        if country.lower() != "cm":
            continue
        try:
            lat, lng = float(item["lat"]), float(item["lon"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise HTTPException(502, "Place search returned invalid coordinates.") from exc
        if not math.isfinite(lat) or not math.isfinite(lng) or not (1.6 <= lat <= 13.2 and 8.3 <= lng <= 16.3):
            raise HTTPException(502, "Place search returned coordinates outside Cameroon.")
        label = item.get("display_name")
        osm_id, osm_type = item.get("osm_id"), item.get("osm_type")
        if (not isinstance(label, str) or not label.strip()
                or type(osm_id) is not int or osm_id <= 0
                or not isinstance(osm_type, str) or osm_type not in {"node", "way", "relation"}):
            raise HTTPException(502, "Place search returned incomplete place information.")
        identifier = f"osm-{osm_type}-{osm_id}"
        if identifier in seen:
            continue
        seen.add(identifier)
        name = item.get("name")
        results.append({
            "id": identifier, "name": name if isinstance(name, str) and name.strip() else label.split(",")[0],
            "display_name": label, "lat": lat, "lng": lng, "source": "openstreetmap",
        })
    return results[:10]


def search_cameroon(query: str, settings: Settings) -> list[Record]:
    global _next_request_at
    normalized = " ".join(query.split())
    if not 3 <= len(normalized) <= 120:
        raise HTTPException(422, "Enter a place name between 3 and 120 characters.")
    if not _lock.acquire(blocking=False):
        raise HTTPException(429, "Another place search is running. Please wait and try again.",
                            headers={"Retry-After": "1"})
    try:
        now = monotonic()
        key = (settings.geocoding_url, normalized.casefold())
        cached = _cache.get(key)
        if cached is not None and now - cached[0] < CACHE_TTL_SECONDS:
            _cache.move_to_end(key)
            return [dict(result) for result in cached[1]]
        if now < _next_request_at:
            raise HTTPException(429, "Please wait a second before searching again.",
                                headers={"Retry-After": str(max(1, math.ceil(_next_request_at - now)))})
        # This local deployment has one search process, shared by all its users.
        _next_request_at = now + 1.0
        try:
            response = httpx.get(
                settings.geocoding_url,
                params={
                    "q": normalized, "format": "jsonv2", "countrycodes": "cm",
                    "addressdetails": 1, "limit": 10, "accept-language": "en",
                },
                headers={"User-Agent": settings.geocoding_user_agent, "Accept": "application/json"},
                timeout=settings.request_timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise HTTPException(503, "Cameroon place search is unavailable. Please try again later.") from exc
        if response.status_code == 429:
            _next_request_at = monotonic() + 10
            raise HTTPException(429, "The place provider is busy. Wait 10 seconds before retrying.",
                                headers={"Retry-After": "10"})
        if response.status_code != 200:
            raise HTTPException(503, "The place provider could not complete this search.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(502, "Place search returned invalid JSON.") from exc
        results = _parse_results(payload)
        _cache[key] = (monotonic(), results)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_CAPACITY:
            _cache.popitem(last=False)
        return [dict(result) for result in results]
    finally:
        _lock.release()

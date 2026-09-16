import math
import threading
from time import monotonic
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import Settings
from app.models.schemas import MapRouteRequest

_lock = threading.Lock()
_next_request_at = 0.0


def _finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _parse_route(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(502, "The routing provider returned an invalid response.")
    if payload.get("code") in ("NoRoute", "NoSegment"):
        raise HTTPException(404, "No road route found between these locations. Try nearby locations connected by roads.")
    routes = payload.get("routes")
    if payload.get("code") != "Ok" or not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
        raise HTTPException(502, "The routing provider returned an invalid route.")
    route = routes[0]
    geometry = route.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        raise HTTPException(502, "The routing provider returned invalid route geometry.")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise HTTPException(502, "The routing provider returned incomplete route geometry.")
    for point in coordinates:
        if (not isinstance(point, list) or len(point) != 2
                or not all(_finite_number(value) for value in point)
                or not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90)):
            raise HTTPException(502, "The routing provider returned invalid route coordinates.")
    distance, duration = route.get("distance"), route.get("duration")
    if not _finite_number(distance) or distance < 0 or not _finite_number(duration) or duration < 0:
        raise HTTPException(502, "The routing provider returned invalid route distance or duration.")
    return {
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "distance_m": distance, "duration_s": duration,
    }


def driving_route(payload: object, settings: Settings) -> dict[str, Any]:
    global _next_request_at
    try:
        request = MapRouteRequest.model_validate(payload)
    except ValidationError as exc:
        # Do not echo precise locations or non-finite JSON numbers in validation errors.
        raise HTTPException(
            422, "Provide numeric origin and destination coordinates within Cameroon "
            "(latitude 1.6 to 13.2, longitude 8.3 to 16.3).",
        ) from exc
    if not _lock.acquire(blocking=False):
        raise HTTPException(429, "Another road route request is running. Please wait and try again.",
                            headers={"Retry-After": "1"})
    try:
        now = monotonic()
        if now < _next_request_at:
            raise HTTPException(429, "Please wait before requesting another road route.",
                                headers={"Retry-After": str(max(1, math.ceil(_next_request_at - now)))})
        # Shared by all users of this single-process local deployment; no location cache.
        _next_request_at = now + 1.0
        coordinates = (
            f"{request.origin.lng},{request.origin.lat};"
            f"{request.destination.lng},{request.destination.lat}"
        )
        try:
            response = httpx.get(
                f"{settings.routing_url.rstrip('/')}/{coordinates}",
                params={
                    "overview": "full", "geometries": "geojson", "steps": "false",
                    "alternatives": "false", "radiuses": "1000;1000",
                },
                headers={"User-Agent": settings.routing_user_agent, "Accept": "application/json"},
                timeout=settings.request_timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise HTTPException(503, "Road routing is unavailable. Please try again later.") from exc
        if response.status_code == 429:
            _next_request_at = monotonic() + 10
            raise HTTPException(429, "The routing provider is busy. Wait 10 seconds before retrying.",
                                headers={"Retry-After": "10"})
        if response.status_code not in {200, 400}:
            raise HTTPException(503, "The routing provider could not complete this road route.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(502, "The routing provider returned invalid JSON.") from exc
        # OSRM can report NoSegment/NoRoute with HTTP 400 as well as HTTP 200.
        result = _parse_route(payload)
        if response.status_code != 200:
            raise HTTPException(503, "The routing provider could not complete this road route.")
        return result
    finally:
        _lock.release()

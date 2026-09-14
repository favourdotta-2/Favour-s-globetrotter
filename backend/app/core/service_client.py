from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import Settings


def service_get(url: str, settings: Settings, authorization: str | None = None) -> Any:
    headers = {"Authorization": authorization} if authorization else {}
    try:
        response = httpx.get(url, headers=headers, timeout=settings.request_timeout_seconds)
    except httpx.RequestError as exc:
        raise HTTPException(503, "A required service is unavailable. Please retry.") from exc
    if response.status_code == 401:
        raise HTTPException(401, "Session expired. Please log in again.")
    if not response.is_success:
        raise HTTPException(503, "A required service could not complete the request.")
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(502, "A required service returned an invalid response.") from exc

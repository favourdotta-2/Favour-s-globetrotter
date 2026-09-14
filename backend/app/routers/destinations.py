from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.core.service_client import service_get
from app.repositories.json_store import JsonStore, get_store
from app.services.destination_service import list_destinations, map_locations, recommendations_for
from app.services.itinerary_service import destination_popularity, list_itineraries

router = APIRouter(tags=["destinations"])


@router.get("/destinations")
def destinations(
    q: str = "",
    tag: str = "",
    mood: str = "",
    continent: str = "",
    max_cost: int | None = Query(default=None, ge=0),
    store: JsonStore = Depends(get_store),
) -> list[dict[str, Any]]:
    return list_destinations(store, query=q, tag=tag, mood=mood, max_cost=max_cost, continent=continent)


@router.get("/recommendations")
def recommendations(
    user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None),
    limit: int = Query(default=6, ge=1, le=50),
) -> list[dict[str, Any]]:
    if settings.service_name == "monolith":
        trips = list_itineraries(user, store)
        popularity = destination_popularity(store)
    else:
        trips = service_get(f"{settings.itinerary_service_url}/api/itineraries", settings, authorization)
        if not isinstance(trips, list) or any(not isinstance(trip, dict) for trip in trips):
            raise HTTPException(502, "Itinerary service returned invalid trips")
        popularity = service_get(
            f"{settings.itinerary_service_url}/api/itineraries/popularity", settings, authorization
        )
        if not isinstance(popularity, dict) or any(
            not isinstance(value, int) or value < 0 for value in popularity.values()
        ):
            raise HTTPException(502, "Itinerary service returned invalid popularity counts")
    return recommendations_for(user, store, trips, popularity, limit)


@router.get("/map/locations")
def locations(store: JsonStore = Depends(get_store)) -> list[dict[str, Any]]:
    return map_locations(store)

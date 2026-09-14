from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.core.service_client import service_get
from app.models.schemas import ItineraryCreate
from app.repositories.json_store import JsonStore, Record, get_store
from app.services import itinerary_service

router = APIRouter(tags=["itineraries"])


def catalogue(
    settings: Settings = Depends(get_settings), store: JsonStore = Depends(get_store)
) -> list[Record]:
    if settings.service_name == "monolith":
        return store.read("destinations")
    destinations = service_get(f"{settings.recommendation_service_url}/api/destinations", settings)
    if not isinstance(destinations, list) or any(
        not isinstance(item, dict) or "id" not in item for item in destinations
    ):
        raise HTTPException(502, "Destination service returned an invalid catalogue")
    return destinations


@router.get("/itineraries")
def all_itineraries(
    user: Record = Depends(get_current_user), store: JsonStore = Depends(get_store)
) -> list[Record]:
    return itinerary_service.list_itineraries(user, store)


@router.get("/itineraries/popularity")
def popularity(
    user: Record = Depends(get_current_user), store: JsonStore = Depends(get_store)
) -> dict[str, int]:
    return itinerary_service.destination_popularity(store)


@router.post("/itineraries", status_code=201)
def add_itinerary(
    payload: ItineraryCreate, user: Record = Depends(get_current_user),
    store: JsonStore = Depends(get_store), destinations: list[Record] = Depends(catalogue),
) -> Record:
    return itinerary_service.create_itinerary(payload, user, store, destinations)


@router.put("/itineraries/{itinerary_id}")
def edit_itinerary(
    itinerary_id: str, payload: ItineraryCreate, user: Record = Depends(get_current_user),
    store: JsonStore = Depends(get_store), destinations: list[Record] = Depends(catalogue),
) -> Record:
    return itinerary_service.update_itinerary(itinerary_id, payload, user, store, destinations)


@router.delete("/itineraries/{itinerary_id}", status_code=204)
def remove_itinerary(
    itinerary_id: str, user: Record = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> Response:
    itinerary_service.delete_itinerary(itinerary_id, user, store)
    return Response(status_code=204)


@router.post("/itineraries/{itinerary_id}/share")
def share(
    itinerary_id: str, user: Record = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> Record:
    return itinerary_service.set_sharing(itinerary_id, user, store, True)


@router.delete("/itineraries/{itinerary_id}/share", status_code=204)
def revoke_share(
    itinerary_id: str, user: Record = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> Response:
    itinerary_service.set_sharing(itinerary_id, user, store, False)
    return Response(status_code=204)


@router.get("/shared/itineraries/{share_id}")
def shared(share_id: str, store: JsonStore = Depends(get_store)) -> Record:
    return itinerary_service.shared_itinerary(share_id, store)

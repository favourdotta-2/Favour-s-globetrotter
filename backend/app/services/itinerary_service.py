import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.models.schemas import ItineraryCreate
from app.repositories.json_store import JsonStore, Record


def trip_fields(payload: ItineraryCreate, catalogue: list[Record]) -> Record:
    by_id = {destination["id"]: destination for destination in catalogue}
    if any(destination_id not in by_id for destination_id in payload.destination_ids):
        raise HTTPException(422, "One or more selected destinations do not exist")
    return {
        **payload.model_dump(mode="json"),
        "destinations": [by_id[destination_id] for destination_id in payload.destination_ids],
    }


def owned_trip(records: list[Record], itinerary_id: str, username: str) -> Record:
    for itinerary in records:
        if itinerary["id"] == itinerary_id and itinerary["username"] == username:
            return itinerary
    raise HTTPException(404, "Itinerary not found")


def create_itinerary(
    payload: ItineraryCreate, user: Record, store: JsonStore, catalogue: list[Record]
) -> Record:
    itinerary = {
        **trip_fields(payload, catalogue),
        "id": str(uuid4()),
        "username": user["username"],
        "share_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return store.append("itineraries", itinerary)


def list_itineraries(user: Record, store: JsonStore) -> list[Record]:
    return [
        itinerary
        for itinerary in store.read("itineraries")
        if itinerary.get("username") == user["username"]
    ]


def destination_popularity(store: JsonStore) -> dict[str, int]:
    counts: dict[str, int] = {}
    for itinerary in store.read("itineraries"):
        for destination_id in set(itinerary.get("destination_ids", [])):
            counts[destination_id] = counts.get(destination_id, 0) + 1
    return counts


def update_itinerary(
    itinerary_id: str, payload: ItineraryCreate, user: Record, store: JsonStore, catalogue: list[Record]
) -> Record:
    fields = trip_fields(payload, catalogue)

    def update(records: list[Record]) -> Record:
        itinerary = owned_trip(records, itinerary_id, user["username"])
        itinerary.update(fields)
        return itinerary

    return store.mutate("itineraries", update)


def delete_itinerary(itinerary_id: str, user: Record, store: JsonStore) -> None:
    def delete(records: list[Record]) -> None:
        records.remove(owned_trip(records, itinerary_id, user["username"]))

    store.mutate("itineraries", delete)


def set_sharing(itinerary_id: str, user: Record, store: JsonStore, enabled: bool) -> Record:
    def update(records: list[Record]) -> Record:
        itinerary = owned_trip(records, itinerary_id, user["username"])
        share_id = (itinerary.get("share_id") or secrets.token_urlsafe(24)) if enabled else None
        itinerary["share_id"] = share_id
        return {"share_id": share_id}

    return store.mutate("itineraries", update)


def shared_itinerary(share_id: str, store: JsonStore) -> dict[str, Any]:
    itinerary = store.find_one("itineraries", "share_id", share_id)
    if itinerary is None:
        raise HTTPException(404, "This shared itinerary was removed or its link was revoked")
    return {key: itinerary[key] for key in (
        "title", "destinations", "start_date", "end_date", "notes", "created_at"
    )}

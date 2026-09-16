from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import Settings
from app.models.schemas import ReviewCreate
from app.repositories.json_store import JsonStore, Record
from app.services.author_service import with_authors


def destination_record(destination_id: str, store: JsonStore) -> Record:
    destination = store.find_one("destinations", "id", destination_id)
    if destination is None:
        raise HTTPException(404, "Destination not found")
    return destination


def destination_detail(destination_id: str, store: JsonStore, settings: Settings) -> Record:
    destination = destination_record(destination_id, store)
    reviews = [review for review in store.read("reviews") if review["destination_id"] == destination_id]
    latest = sorted(reviews, key=lambda review: review["updated_at"], reverse=True)[:100]
    return {
        **destination,
        "rating_average": round(sum(review["rating"] for review in reviews) / len(reviews), 1) if reviews else None,
        "review_count": len(reviews),
        "reviews": with_authors(latest, store, settings),
    }


def save_review(destination_id: str, payload: ReviewCreate, user: Record, store: JsonStore) -> Record:
    destination_record(destination_id, store)
    now = datetime.now(timezone.utc).isoformat()

    def update(reviews: list[Record]) -> Record:
        for review in reviews:
            if review["destination_id"] == destination_id and review["username"] == user["username"]:
                review.update(payload.model_dump(), updated_at=now)
                return review
        review = {
            "id": str(uuid4()), "destination_id": destination_id, "username": user["username"],
            **payload.model_dump(), "created_at": now, "updated_at": now,
        }
        reviews.append(review)
        return review

    return store.mutate("reviews", update)


def remove_review(destination_id: str, user: Record, store: JsonStore) -> None:
    destination_record(destination_id, store)

    def delete(reviews: list[Record]) -> None:
        for review in reviews:
            if review["destination_id"] == destination_id and review["username"] == user["username"]:
                reviews.remove(review)
                return
        raise HTTPException(404, "You have not reviewed this destination")

    store.mutate("reviews", delete)

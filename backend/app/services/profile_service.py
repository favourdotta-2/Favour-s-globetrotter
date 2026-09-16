from typing import Any

from fastapi import HTTPException

from datetime import datetime, timezone

from app.models.schemas import AppRatingCreate, ProfileUpdate
from app.services.auth_service import public_user
from app.repositories.json_store import JsonStore


def update_profile(payload: ProfileUpdate, user: dict[str, Any], store: JsonStore) -> dict[str, Any]:
    def update(users: list[dict[str, Any]]) -> dict[str, Any]:
        for current in users:
            if current["username"] == user["username"]:
                current.update(payload.model_dump())
                return public_user(current)
        raise HTTPException(404, "Profile not found")

    return store.mutate("users", update)


def save_app_rating(payload: AppRatingCreate, user: dict[str, Any], store: JsonStore) -> dict[str, Any]:
    def update(ratings: list[dict[str, Any]]) -> dict[str, Any]:
        record = {"username": user["username"], **payload.model_dump(),
                  "updated_at": datetime.now(timezone.utc).isoformat()}
        for index, rating in enumerate(ratings):
            if rating["username"] == user["username"]:
                ratings[index] = record
                return record
        ratings.append(record)
        return record

    return store.mutate("app_ratings", update)

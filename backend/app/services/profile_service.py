from typing import Any

from fastapi import HTTPException

from app.models.schemas import ProfileUpdate
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

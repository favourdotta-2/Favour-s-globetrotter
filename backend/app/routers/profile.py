from typing import Any

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.schemas import ProfileUpdate
from app.repositories.json_store import JsonStore, get_store
from app.services.auth_service import public_user
from app.services.profile_service import update_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
def get_profile(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return public_user(user)


@router.put("")
def save_profile(
    payload: ProfileUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> dict[str, Any]:
    return update_profile(payload, user, store)

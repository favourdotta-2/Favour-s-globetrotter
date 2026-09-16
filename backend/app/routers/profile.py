from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.core.security import get_current_user
from app.models.schemas import AppRatingCreate, ProfileUpdate
from app.repositories.json_store import JsonStore, get_store
from app.services.auth_service import public_user
from app.services.profile_service import save_app_rating, update_profile
from app.services.author_service import public_authors
from app.services.media_service import media_path, read_upload, save_avatar

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


@router.get("/public")
def authors(
    usernames: str = Query(min_length=1, max_length=4100),
    store: JsonStore = Depends(get_store),
) -> dict[str, dict[str, Any]]:
    requested = set(usernames.split(","))
    if len(requested) > 100:
        from fastapi import HTTPException
        raise HTTPException(422, "At most 100 author profiles can be requested at once")
    return public_authors(requested, store)


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> dict[str, Any]:
    try:
        content = await read_upload(file)
    finally:
        await file.close()
    return await run_in_threadpool(save_avatar, content, file.content_type or "", user, store)


@router.get("/avatars/{filename}")
def avatar(filename: str, store: JsonStore = Depends(get_store)) -> FileResponse:
    return FileResponse(media_path(store, "avatars", filename), media_type="image/webp")


@router.get("/app-rating")
def my_app_rating(
    user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> dict[str, Any] | None:
    return store.find_one("app_ratings", "username", user["username"])


@router.put("/app-rating")
def rate_app(
    payload: AppRatingCreate, user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> dict[str, Any]:
    return save_app_rating(payload, user, store)

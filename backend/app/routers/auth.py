from typing import Any

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.models.schemas import AuthResponse, LoginRequest, UserCreate
from app.repositories.json_store import JsonStore, get_store
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=201)
def signup(
    payload: UserCreate,
    store: JsonStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return auth_service.signup(payload, store, settings)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    store: JsonStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return auth_service.login(payload, store, settings)


@router.get("/me")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return auth_service.public_user(user)

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.schemas import LoginRequest, UserCreate
from app.repositories.json_store import JsonStore


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "full_name": user.get("full_name", ""),
        "preferences": user.get("preferences", []),
        "bio": user.get("bio", ""),
        "home_city": user.get("home_city", ""),
        "created_at": user.get("created_at", ""),
        "avatar_url": user.get("avatar_url"),
    }


def signup(payload: UserCreate, store: JsonStore, settings: Settings) -> dict[str, Any]:
    username = payload.username.strip().lower()
    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": str(uuid4()),
        "username": username,
        "full_name": payload.full_name.strip(),
        "password_hash": hash_password(payload.password),
        "preferences": payload.preferences,
        "bio": "",
        "home_city": "",
        "created_at": now,
    }
    def insert(users: list[dict[str, Any]]) -> None:
        if any(existing["username"] == username for existing in users):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
        users.append(user)

    store.mutate("users", insert)
    return {"token": create_access_token(username, settings), "user": public_user(user)}


def login(payload: LoginRequest, store: JsonStore, settings: Settings) -> dict[str, Any]:
    username = payload.username.strip().lower()
    user = store.find_one("users", "username", username)
    if user is None or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {"token": create_access_token(username, settings), "user": public_user(user)}

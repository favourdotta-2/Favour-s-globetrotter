from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from werkzeug.security import check_password_hash, generate_password_hash

from app.core.config import Settings, get_settings
from app.core.service_client import service_get
from app.models.schemas import PublicUser
from app.repositories.json_store import JsonStore, get_store
from pydantic import ValidationError

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def create_access_token(username: str, settings: Settings) -> str:
    if settings.secret_key is None:
        raise RuntimeError("SECRET_KEY must be configured for the user service")
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> str:
    if settings.secret_key is None:
        raise RuntimeError("SECRET_KEY must be configured for the user service")
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )
    return username


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
    store: JsonStore = Depends(get_store),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    if settings.service_name not in {"monolith", "user"}:
        profile = service_get(
            f"{settings.user_service_url}/api/auth/me",
            settings,
            f"Bearer {credentials.credentials}",
        )
        try:
            return PublicUser.model_validate(profile).model_dump()
        except ValidationError as exc:
            raise HTTPException(502, "User service returned an invalid profile") from exc

    username = decode_access_token(credentials.credentials, settings)
    user = store.find_one("users", "username", username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session no longer valid")
    return user

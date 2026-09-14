from typing import Any

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.schemas import ChatMessageCreate
from app.repositories.json_store import JsonStore, get_store
from app.services.chat_service import create_message, list_messages

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/messages")
def messages(
    user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> list[dict[str, Any]]:
    return list_messages(store)


@router.post("/messages", status_code=201)
def post_message(
    payload: ChatMessageCreate,
    user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> dict[str, Any]:
    return create_message(payload, user, store)

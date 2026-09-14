from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.schemas import ChatMessageCreate
from app.repositories.json_store import JsonStore


def list_messages(store: JsonStore) -> list[dict[str, Any]]:
    return sorted(store.read("chat_messages"), key=lambda message: message.get("created_at", ""))[-100:]


def create_message(payload: ChatMessageCreate, user: dict[str, Any], store: JsonStore) -> dict[str, Any]:
    message = {
        "id": str(uuid4()),
        "username": user["username"],
        "text": payload.text.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return store.append("chat_messages", message)

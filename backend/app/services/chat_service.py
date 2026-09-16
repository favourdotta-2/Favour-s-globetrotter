from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.models.schemas import ChatMessageCreate
from app.repositories.json_store import JsonStore, StorageError
from app.services.media_service import discard_media, public_media, save_attachment


def list_messages(store: JsonStore) -> list[dict[str, Any]]:
    messages = sorted(store.read("chat_messages"), key=lambda message: message.get("created_at", ""))[-100:]
    media = {record["id"]: public_media(record) for record in store.read("chat_media")}
    return [{**message, "media": media.get(message.get("media_id"))} for message in messages]


def create_message(payload: ChatMessageCreate, user: dict[str, Any], store: JsonStore) -> dict[str, Any]:
    attachment = None
    if payload.media_id:
        attachment = store.find_one("chat_media", "id", payload.media_id)
        if attachment is None or attachment["username"] != user["username"]:
            raise HTTPException(404, "Your attachment was not found. Upload it again.")
    message = {
        "id": str(uuid4()),
        "username": user["username"],
        "text": payload.text.strip(),
        "sticker": payload.sticker,
        "media_id": payload.media_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    store.append("chat_messages", message)
    return {**message, "media": public_media(attachment) if attachment else None}


def create_uploaded_message(
    content: bytes, mime_type: str, name: str, text: str, user: dict[str, Any], store: JsonStore
) -> dict[str, Any]:
    attachment = save_attachment(content, mime_type, name, user, store)
    try:
        return create_message(ChatMessageCreate(text=text, media_id=attachment["id"]), user, store)
    except (StorageError, HTTPException):
        def rollback(records: list[dict[str, Any]]) -> None:
            for record in records:
                if record["id"] == attachment["id"]:
                    discard_media(store.data_dir / "uploads" / "chat" / record["filename"])
                    records.remove(record)
                    return
        store.mutate("chat_media", rollback)
        raise

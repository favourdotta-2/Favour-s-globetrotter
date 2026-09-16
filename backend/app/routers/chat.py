from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.models.schemas import ChatMessageCreate, PublicAuthor
from app.repositories.json_store import JsonStore, get_store
from app.services.chat_service import create_message, create_uploaded_message, list_messages
from app.services.author_service import with_authors
from app.services.media_service import get_attachment, media_path, read_upload, save_attachment

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/messages")
def messages(
    user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    return with_authors(list_messages(store), store, settings)


@router.post("/messages", status_code=201)
def post_message(
    payload: ChatMessageCreate,
    user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return {**create_message(payload, user, store), "author": PublicAuthor.model_validate(user).model_dump()}


@router.post("/media", status_code=201)
async def upload_media(
    file: UploadFile = File(...), user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> dict[str, Any]:
    try:
        content = await read_upload(file)
    finally:
        await file.close()
    return await run_in_threadpool(
        save_attachment, content, file.content_type or "", file.filename or "attachment", user, store
    )


@router.post("/messages/upload", status_code=201)
async def post_uploaded_message(
    file: UploadFile = File(...), text: str = Form(default="", max_length=500),
    user: dict[str, Any] = Depends(get_current_user), store: JsonStore = Depends(get_store),
) -> dict[str, Any]:
    try:
        content = await read_upload(file)
    finally:
        await file.close()
    message = await run_in_threadpool(
        create_uploaded_message, content, file.content_type or "", file.filename or "attachment",
        text, user, store,
    )
    return {**message, "author": PublicAuthor.model_validate(user).model_dump()}


@router.get("/media/{media_id}")
def attachment(
    media_id: str, user: dict[str, Any] = Depends(get_current_user),
    store: JsonStore = Depends(get_store),
) -> FileResponse:
    record = get_attachment(media_id, user, store)
    return FileResponse(
        media_path(store, "chat", record["filename"]), media_type=record["mime_type"],
        filename=record["name"], content_disposition_type="inline",
    )

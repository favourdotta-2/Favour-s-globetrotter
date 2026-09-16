import io
import logging
import os
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import av
from av.error import FFmpegError
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.body_limit import MAX_FILE_BYTES
from app.repositories.json_store import JsonStore, Record, StorageError

IMAGE_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP", "image/gif": "GIF"}
VIDEO_TYPES = {"video/mp4", "video/webm"}
MAX_PIXELS = 16_777_216
logger = logging.getLogger("uvicorn.error")


async def read_upload(upload: UploadFile) -> bytes:
    content = bytearray()
    while chunk := await upload.read(64 * 1024):
        content.extend(chunk)
        if len(content) >= MAX_FILE_BYTES:
            raise HTTPException(413, "The file must be strictly less than 5 MB (5,000,000 bytes).")
    if not content:
        raise HTTPException(422, "The uploaded file is empty.")
    return bytes(content)


def normalize_image(content: bytes, mime_type: str, *, avatar: bool) -> bytes:
    if mime_type not in IMAGE_TYPES:
        raise HTTPException(415, "Choose a JPEG, PNG, WebP, or GIF image.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format != IMAGE_TYPES[mime_type]:
                    raise HTTPException(415, "The image content does not match its file type.")
                if image.width * image.height > MAX_PIXELS:
                    raise HTTPException(422, "Images must be no larger than 16 megapixels.")
                image.load()
                normalized = ImageOps.exif_transpose(image).convert("RGBA")
                if avatar:
                    normalized = ImageOps.fit(normalized, (512, 512))
                else:
                    normalized.thumbnail((2048, 2048))
                normalized.info.clear()
                output = io.BytesIO()
                normalized.save(output, format="WEBP", quality=85)
                data = output.getvalue()
                if len(data) >= MAX_FILE_BYTES:
                    raise HTTPException(422, "The processed image is too large; choose a smaller image.")
                return data
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(422, "This image could not be decoded. Please choose a valid image.") from exc


def validate_video(content: bytes, mime_type: str) -> str:
    if mime_type not in VIDEO_TYPES:
        raise HTTPException(415, "Choose an H.264 MP4 or a VP8/VP9 WebM video.")
    is_mp4 = len(content) >= 12 and content[4:8] == b"ftyp"
    is_webm = content.startswith(b"\x1a\x45\xdf\xa3")
    if not ((mime_type == "video/mp4" and is_mp4) or (mime_type == "video/webm" and is_webm)):
        raise HTTPException(415, "The video content does not match its file type.")
    try:
        with av.open(io.BytesIO(content), mode="r", options={"protocol_whitelist": "pipe"}) as container:
            if not container.streams.video:
                raise HTTPException(422, "The file contains no video track.")
            stream = container.streams.video[0]
            if stream.width <= 0 or stream.height <= 0 or stream.width * stream.height > MAX_PIXELS:
                raise HTTPException(422, "Video dimensions must be valid and no larger than 16 megapixels.")
            expected_codecs = {"h264"} if is_mp4 else {"vp8", "vp9"}
            if stream.codec_context.name not in expected_codecs:
                raise HTTPException(415, "Use an H.264 MP4 or VP8/VP9 WebM video for browser playback.")
            if next(container.decode(video=0), None) is None:
                raise HTTPException(422, "The video has no decodable frames.")
    except (FFmpegError, ValueError, OSError) as exc:
        raise HTTPException(422, "This video could not be decoded. Please choose a valid video.") from exc
    return "mp4" if is_mp4 else "webm"


def write_media(directory: Path, filename: str, content: bytes) -> Path:
    path = directory / filename
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise StorageError("Could not persist the uploaded file.") from exc
    return path


def discard_media(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Could not clean up an obsolete uploaded file.")


def media_path(store: JsonStore, category: str, filename: str) -> Path:
    if category not in {"avatars", "chat"} or not re.fullmatch(r"[a-f0-9]{32}\.(webp|mp4|webm)", filename):
        raise HTTPException(404, "Media not found")
    path = store.data_dir / "uploads" / category / filename
    if not path.is_file():
        raise HTTPException(404, "Media not found")
    return path


def save_avatar(content: bytes, mime_type: str, user: Record, store: JsonStore) -> Record:
    from app.services.auth_service import public_user

    image = normalize_image(content, mime_type, avatar=True)
    filename = f"{uuid4().hex}.webp"
    path = write_media(store.data_dir / "uploads" / "avatars", filename, image)
    previous_url: str | None = None

    def update(users: list[Record]) -> Record:
        nonlocal previous_url
        for current in users:
            if current["username"] == user["username"]:
                previous_url = current.get("avatar_url")
                current["avatar_url"] = f"/api/profile/avatars/{filename}"
                return public_user(current)
        raise HTTPException(404, "Profile not found")

    try:
        result = store.mutate("users", update)
    except (StorageError, HTTPException):
        discard_media(path)
        raise
    if previous_url:
        old_name = previous_url.rsplit("/", 1)[-1]
        if re.fullmatch(r"[a-f0-9]{32}\.webp", old_name):
            discard_media(store.data_dir / "uploads" / "avatars" / old_name)
    return result


def save_attachment(content: bytes, mime_type: str, name: str, user: Record, store: JsonStore) -> Record:
    if mime_type in IMAGE_TYPES:
        content = normalize_image(content, mime_type, avatar=False)
        extension, kind, served_type = "webp", "image", "image/webp"
    elif mime_type in VIDEO_TYPES:
        extension = validate_video(content, mime_type)
        kind, served_type = "video", mime_type
    else:
        raise HTTPException(415, "Choose an image (JPEG, PNG, WebP, GIF) or video (MP4, WebM).")
    media_id = uuid4().hex
    path = write_media(store.data_dir / "uploads" / "chat", f"{media_id}.{extension}", content)
    record = {
        "id": media_id, "username": user["username"], "filename": path.name,
        "name": re.sub(r"[\x00-\x1f\x7f]", "_", name.replace("\\", "/").rsplit("/", 1)[-1])[:120] or "attachment",
        "kind": kind, "mime_type": served_type, "size": len(content),
        "url": f"/api/chat/media/{media_id}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        store.append("chat_media", record)
    except StorageError:
        discard_media(path)
        raise
    return public_media(record)


def public_media(record: Record) -> Record:
    return {key: record[key] for key in ("id", "name", "kind", "mime_type", "size", "url")}


def get_attachment(media_id: str, user: Record, store: JsonStore) -> Record:
    record = store.find_one("chat_media", "id", media_id)
    if record is None:
        raise HTTPException(404, "Attachment not found")
    if record["username"] != user["username"] and not any(
        message.get("media_id") == media_id for message in store.read("chat_messages")
    ):
        raise HTTPException(404, "Attachment not found")
    return record

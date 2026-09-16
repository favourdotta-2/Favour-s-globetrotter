from urllib.parse import urlencode

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from app.core.config import Settings
from app.core.service_client import service_get
from app.models.schemas import PublicAuthor
from app.repositories.json_store import JsonStore, Record


def public_authors(usernames: set[str], store: JsonStore) -> dict[str, Record]:
    return {
        user["username"]: PublicAuthor.model_validate(user).model_dump()
        for user in store.read("users") if user["username"] in usernames
    }


def authors_for(usernames: set[str], store: JsonStore, settings: Settings) -> dict[str, Record]:
    if not usernames:
        return {}
    if settings.service_name in {"monolith", "user"}:
        return public_authors(usernames, store)
    query = urlencode({"usernames": ",".join(sorted(usernames))})
    response = service_get(f"{settings.user_service_url}/api/profile/public?{query}", settings)
    try:
        authors = TypeAdapter(dict[str, PublicAuthor]).validate_python(response)
    except ValidationError as exc:
        raise HTTPException(502, "The user service returned invalid author profiles.") from exc
    return {username: author.model_dump() for username, author in authors.items()}


def with_authors(records: list[Record], store: JsonStore, settings: Settings) -> list[Record]:
    authors = authors_for({record["username"] for record in records}, store, settings)
    return [
        {**record, "author": authors.get(record["username"], {
            "username": record["username"], "full_name": "", "avatar_url": None,
        })}
        for record in records
    ]

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ServiceName = Literal["monolith", "user", "itinerary", "recommendation", "chat", "gateway"]
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        populate_by_name=True,
        env_file=(str(BACKEND_DIR.parent / ".env"), str(BACKEND_DIR / ".env")),
        extra="ignore",
    )

    app_name: str = "GlobeTrotter API"
    api_prefix: str = "/api"
    service_name: ServiceName = "monolith"
    secret_key: str | None = Field(default=None, min_length=32)
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")
    data_dir: Path = BACKEND_DIR / "data"
    catalog_path: Path = BACKEND_DIR / "data" / "destinations.json"
    user_service_url: str = "http://user:8000"
    itinerary_service_url: str = "http://itinerary:8000"
    recommendation_service_url: str = "http://recommendation:8000"
    chat_service_url: str = "http://chat:8000"
    request_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    geocoding_url: str = "https://nominatim.openstreetmap.org/search"
    geocoding_user_agent: str = (
        "GlobeTrotterCameroon/1.0 (https://github.com/favourdotta-2/Favour-s-globetrotter)"
    )
    routing_url: str = "https://router.project-osrm.org/route/v1/driving"
    routing_user_agent: str = (
        "GlobeTrotterCameroon/1.0 (https://github.com/favourdotta-2/Favour-s-globetrotter)"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

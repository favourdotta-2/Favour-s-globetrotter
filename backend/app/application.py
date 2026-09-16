import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.body_limit import BodyLimitMiddleware
from app.core.service_client import service_get
from app.repositories.json_store import JsonStore, StorageError
from app.routers import auth, chat, destinations, gateway, itineraries, profile

logger = logging.getLogger("uvicorn.error")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.service_name in {"monolith", "user"} and settings.secret_key is None:
        raise RuntimeError("Set SECRET_KEY to a random value of at least 32 characters before starting.")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            app.state.http_client = client
            yield

    app = FastAPI(title=f"GlobeTrotter - {settings.service_name}", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(BodyLimitMiddleware)
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        started = time.perf_counter()
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            "service=%s request_id=%s method=%s status=%d duration_ms=%.1f",
            settings.service_name, request.state.request_id, request.method,
            response.status_code, (time.perf_counter() - started) * 1000,
        )
        return response

    @app.exception_handler(StorageError)
    async def storage_error(request: Request, exc: StorageError):
        logger.error("service=%s storage_error=%s", settings.service_name, exc, exc_info=exc)
        return JSONResponse(
            status_code=503, content={"detail": "Data storage is unavailable. Please contact the administrator."}
        )

    @app.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    @app.get("/ready", tags=["operations"])
    def ready() -> dict[str, str]:
        store = JsonStore(settings.data_dir, settings.catalog_path)
        collections = {
            "monolith": ["users", "itineraries", "chat_messages", "destinations", "reviews", "app_ratings", "chat_media"],
            "user": ["users", "app_ratings"], "itinerary": ["itineraries"],
            "recommendation": ["destinations", "reviews"], "chat": ["chat_messages", "chat_media"], "gateway": [],
        }
        for collection in collections[settings.service_name]:
            store.read(collection)
        if settings.service_name == "gateway":
            for url in (
                settings.user_service_url, settings.itinerary_service_url,
                settings.recommendation_service_url, settings.chat_service_url,
            ):
                service_get(f"{url}/ready", settings)
        return {"status": "ready", "service": settings.service_name}

    service_routers = {
        "user": [auth.router, profile.router],
        "itinerary": [itineraries.router],
        "recommendation": [destinations.router],
        "chat": [chat.router],
    }
    if settings.service_name == "gateway":
        app.include_router(gateway.router)
    else:
        selected = (list(service_routers) if settings.service_name == "monolith"
                    else [settings.service_name])
        for name in selected:
            for router in service_routers[name]:
                app.include_router(router, prefix=settings.api_prefix)

    if settings.service_name == "monolith":
        for path, endpoint, methods in (
            ("/register", auth.signup, ["POST"]),
            ("/login", auth.login, ["POST"]),
            ("/destinations", destinations.destinations, ["GET"]),
            ("/recommendations", destinations.recommendations, ["GET"]),
            ("/itineraries", itineraries.all_itineraries, ["GET"]),
            ("/itineraries", itineraries.add_itinerary, ["POST"]),
        ):
            app.add_api_route(
                path, endpoint, methods=methods, tags=["phase-one"],
                status_code=201 if path in {"/register", "/itineraries"} and methods == ["POST"] else 200,
            )
    return app

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from app.core.config import Settings
from app.core.body_limit import MAX_REQUEST_BYTES

router = APIRouter()
ALIASES = {
    "register": "auth/signup",
    "login": "auth/login",
    "destinations": "destinations",
    "recommendations": "recommendations",
    "itineraries": "itineraries",
}


def upstream(path: str, settings: Settings) -> str:
    segment = path.split("/", 1)[0]
    if segment in {"auth", "profile"}:
        return settings.user_service_url
    if segment in {"destinations", "recommendations", "map"}:
        return settings.recommendation_service_url
    if segment in {"itineraries", "shared"}:
        return settings.itinerary_service_url
    if segment == "chat":
        return settings.chat_service_url
    raise HTTPException(404, "Endpoint not found")


async def forward(request: Request, path: str) -> Response:
    settings = request.app.state.settings
    base_url = upstream(path, settings)
    headers = {key: value for key, value in request.headers.items()
               if key.lower() in {"authorization", "content-type", "accept", "range", "if-range"}}
    headers["x-request-id"] = request.state.request_id
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_REQUEST_BYTES:
            raise HTTPException(413, "Each uploaded file must be less than 5 MB.")
    try:
        response = await request.app.state.http_client.request(
            request.method, f"{base_url}/api/{path}",
            params=request.query_params.multi_items(), content=bytes(body), headers=headers,
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "The requested service timed out. Please retry.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, "The requested service is unavailable. Please retry.") from exc
    response_headers = {key: value for key, value in response.headers.items()
                        if key.lower() in {
                            "content-type", "www-authenticate", "retry-after", "content-range",
                            "accept-ranges", "content-disposition",
                        }}
    return Response(response.content, status_code=response.status_code, headers=response_headers)


@router.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request) -> Response:
    return await forward(request, path)


@router.api_route("/{alias}", methods=["GET", "POST"])
async def phase_one_alias(alias: str, request: Request) -> Response:
    if alias not in ALIASES:
        raise HTTPException(404, "Endpoint not found")
    return await forward(request, ALIASES[alias])

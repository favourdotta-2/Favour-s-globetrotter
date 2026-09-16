import json
import logging
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.application import create_app
from app.core.config import Settings
from app.repositories.json_store import JsonStore
from app.services import routing_service as routing

REQUEST = {
    "origin": {"lat": 3.86, "lng": 11.51},
    "destination": {"lat": 3.87, "lng": 11.52},
}
COORDINATES = [[11.51, 3.86], [11.515, 3.865], [11.52, 3.87]]
RESULT = {
    "geometry": {"type": "LineString", "coordinates": COORDINATES},
    "distance_m": 1650.5, "duration_s": 240.25,
}


def provider_payload(**changes):
    return {
        "code": "Ok",
        "routes": [{
            "geometry": {"type": "LineString", "coordinates": COORDINATES},
            "distance": 1650.5, "duration": 240.25,
            **changes,
        }],
        "waypoints": [{"name": "Not included in the API response"}],
    }


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(routing, "_lock", threading.Lock()))
        self.enterContext(patch.object(routing, "_next_request_at", 0.0))
        self.clock = self.enterContext(patch.object(routing, "monotonic", return_value=100.0))
        self.get = self.enterContext(patch.object(routing.httpx, "get"))
        self.get.return_value = httpx.Response(200, json=provider_payload())
        self.settings = Settings(service_name="recommendation", _env_file=None)
        self.enterContext(patch.object(
            JsonStore, "__init__", side_effect=AssertionError("Routing must not access persistent storage"),
        ))

    def assert_error(self, status, payload=REQUEST):
        with self.assertRaises(HTTPException) as error:
            routing.driving_route(payload, self.settings)
        self.assertEqual(error.exception.status_code, status)
        return error.exception

    def test_request_contract_coordinate_order_and_provider_options(self):
        self.assertEqual(routing.driving_route(REQUEST, self.settings), RESULT)
        self.get.assert_called_once_with(
            f"{self.settings.routing_url}/11.51,3.86;11.52,3.87",
            params={
                "overview": "full", "geometries": "geojson", "steps": "false",
                "alternatives": "false", "radiuses": "1000;1000",
            },
            headers={"User-Agent": self.settings.routing_user_agent, "Accept": "application/json"},
            timeout=self.settings.request_timeout_seconds,
        )

    def test_provider_environment_defaults_and_overrides(self):
        with patch.dict("os.environ", {}, clear=True):
            defaults = Settings(service_name="recommendation", _env_file=None)
        self.assertEqual(defaults.routing_url, "https://router.project-osrm.org/route/v1/driving")
        self.assertEqual(
            defaults.routing_user_agent,
            "GlobeTrotterCameroon/1.0 (https://github.com/favourdotta-2/Favour-s-globetrotter)",
        )
        with patch.dict("os.environ", {
            "ROUTING_URL": "https://routing.example/route/v1/driving/",
            "ROUTING_USER_AGENT": "RouteTests/1.0", "REQUEST_TIMEOUT_SECONDS": "2",
        }):
            settings = Settings(service_name="recommendation", _env_file=None)
        routing.driving_route(REQUEST, settings)
        self.assertEqual(self.get.call_args.args, (
            "https://routing.example/route/v1/driving/11.51,3.86;11.52,3.87",
        ))
        self.assertEqual(self.get.call_args.kwargs["headers"]["User-Agent"], "RouteTests/1.0")
        self.assertEqual(self.get.call_args.kwargs["timeout"], 2)

    def test_invalid_coordinates_and_shapes_do_not_contact_provider_or_consume_quota(self):
        invalid_requests = [
            None, [], 10, "origin", {}, {"origin": REQUEST["origin"]},
            {**REQUEST, "destination": None},
            {**REQUEST, "origin": []},
            {**REQUEST, "extra": "not part of the contract"},
            {**REQUEST, "origin": {"lat": 3.86}},
        ]
        for endpoint in ("origin", "destination"):
            for field, values in (
                ("lat", (1.599, 13.201, "3.86", True, None, [], {}, float("nan"), float("inf"), -float("inf"))),
                ("lng", (8.299, 16.301, "11.51", False, None, [], {}, float("nan"), float("inf"), -float("inf"))),
            ):
                for value in values:
                    invalid_requests.append({
                        **REQUEST, endpoint: {**REQUEST[endpoint], field: value},
                    })
            invalid_requests.append({**REQUEST, endpoint: {**REQUEST[endpoint], "altitude": 10}})
        for payload in invalid_requests:
            with self.subTest(payload=payload):
                error = self.assert_error(422, payload)
                self.assertIn("within Cameroon", error.detail)
                self.assertEqual(routing._next_request_at, 0)
        self.get.assert_not_called()

    def test_inclusive_cameroon_bounds_and_integer_coordinates(self):
        requests = (
            {"origin": {"lat": 1.6, "lng": 8.3}, "destination": {"lat": 13.2, "lng": 16.3}},
            {"origin": {"lat": 4, "lng": 12}, "destination": {"lat": 5, "lng": 13}},
        )
        for payload in requests:
            with self.subTest(payload=payload):
                self.clock.return_value += 1
                self.assertEqual(routing.driving_route(payload, self.settings), RESULT)

    def test_routes_are_not_cached_and_throttle_is_shared_across_settings(self):
        routing.driving_route(REQUEST, self.settings)
        other_settings = self.settings.model_copy(update={"routing_url": "https://routing.example/driving"})
        with self.assertRaises(HTTPException) as error:
            routing.driving_route(REQUEST, other_settings)
        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(error.exception.headers["Retry-After"], "1")
        self.get.assert_called_once()
        self.clock.return_value = 101.0
        self.get.return_value = httpx.Response(200, json=provider_payload(distance=1700))
        self.assertEqual(routing.driving_route(REQUEST, other_settings)["distance_m"], 1700)
        self.assertEqual(self.get.call_count, 2)

    def test_throttle_blocks_requests_until_one_second_has_passed(self):
        routing.driving_route(REQUEST, self.settings)
        self.clock.return_value = 100.999
        self.assertEqual(self.assert_error(429).headers["Retry-After"], "1")
        self.get.assert_called_once()
        self.clock.return_value = 101.0
        routing.driving_route(REQUEST, self.settings)
        self.assertEqual(self.get.call_count, 2)

    def test_in_flight_request_rejects_concurrency_even_after_one_second(self):
        started, release = threading.Event(), threading.Event()

        def respond(*args, **kwargs):
            started.set()
            self.assertTrue(release.wait(5), "Test did not release the provider request")
            return httpx.Response(200, json=provider_payload())

        self.get.side_effect = respond
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(routing.driving_route, REQUEST, self.settings)
            try:
                self.assertTrue(started.wait(2), "Provider request did not start")
                self.clock.return_value = 102.0
                self.assertEqual(self.assert_error(429).headers["Retry-After"], "1")
                self.get.assert_called_once()
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=2), RESULT)
        self.assertFalse(routing._lock.locked())
        self.assertEqual(routing.driving_route(REQUEST, self.settings), RESULT)
        self.assertEqual(self.get.call_count, 2)

    def test_provider_429_starts_ten_second_cooldown_without_retrying(self):
        self.get.return_value = httpx.Response(429)
        error = self.assert_error(429)
        self.assertEqual(error.headers["Retry-After"], "10")
        self.assertEqual(routing._next_request_at, 110.0)
        for now, retry_after in ((100.1, "10"), (109.1, "1")):
            self.clock.return_value = now
            self.assertEqual(self.assert_error(429).headers["Retry-After"], retry_after)
        self.get.assert_called_once()
        self.clock.return_value = 110.0
        self.get.return_value = httpx.Response(200, json=provider_payload())
        self.assertEqual(routing.driving_route(REQUEST, self.settings), RESULT)
        self.assertEqual(self.get.call_count, 2)

    def test_network_failures_and_http_errors_do_not_retry_and_release_lock(self):
        failures = (
            httpx.ConnectError("Offline"), httpx.ReadTimeout("Timeout"),
            httpx.ConnectTimeout("Timeout"), httpx.RemoteProtocolError("Disconnected"),
            httpx.Response(503), httpx.Response(500), httpx.Response(403),
            httpx.Response(302, headers={"Location": "https://other.example"}),
            httpx.Response(400, json=provider_payload()),
        )
        for failure in failures:
            with self.subTest(failure=failure):
                self.clock.return_value += 20
                self.get.reset_mock()
                self.get.side_effect = failure if isinstance(failure, Exception) else None
                if isinstance(failure, httpx.Response):
                    self.get.return_value = failure
                self.assert_error(503)
                self.get.assert_called_once()
                self.assertFalse(routing._lock.locked())

    def test_failed_provider_request_still_consumes_one_second_quota(self):
        self.get.side_effect = httpx.ConnectError("Offline")
        self.assert_error(503)
        self.assert_error(429)
        self.get.assert_called_once()
        self.clock.return_value = 101.0
        self.get.side_effect = None
        self.assertEqual(routing.driving_route(REQUEST, self.settings), RESULT)

    def test_no_route_and_no_segment_are_clear_non_success_responses(self):
        for status in (200, 400):
            for code in ("NoRoute", "NoSegment"):
                with self.subTest(status=status, code=code):
                    self.clock.return_value += 1
                    self.get.return_value = httpx.Response(status, json={
                        "code": code, "message": "Untrusted provider message",
                    })
                    error = self.assert_error(404)
                    self.assertIn("No road route found", error.detail)
                    self.assertNotIn("Untrusted", error.detail)
                    self.assertFalse(routing._lock.locked())

    def test_malformed_provider_json_and_payloads_are_bad_gateway_errors(self):
        invalid = [
            None, [], {}, {"code": ["Ok"]}, {"code": "InvalidQuery"},
            {"code": "Ok"}, {"code": "Ok", "routes": None},
            {"code": "Ok", "routes": []}, {"code": "Ok", "routes": [None]},
            provider_payload(geometry=None),
            provider_payload(geometry={"type": "MultiLineString", "coordinates": [COORDINATES]}),
        ]
        for coordinates in (None, {}, [], [COORDINATES[0]], [None, COORDINATES[1]],
                            [[11, 3, 1], [12, 4]], [["11", 3], [12, 4]]):
            invalid.append(provider_payload(geometry={"type": "LineString", "coordinates": coordinates}))
        for axis, values in (
            (0, (-180.001, 180.001, True, None, float("nan"), float("inf"), 10 ** 400)),
            (1, (-90.001, 90.001, False, None, float("nan"), -float("inf"), 10 ** 400)),
        ):
            for value in values:
                point = [11, 3]
                point[axis] = value
                invalid.append(provider_payload(geometry={
                    "type": "LineString", "coordinates": [point, [12, 4]],
                }))
        for field in ("distance", "duration"):
            for value in (-1, "100", True, None, [], {}, float("nan"), float("inf"), 10 ** 400):
                invalid.append(provider_payload(**{field: value}))
            missing = provider_payload()
            del missing["routes"][0][field]
            invalid.append(missing)
        for payload in invalid:
            with self.subTest(payload=payload):
                self.clock.return_value += 1
                self.get.return_value = httpx.Response(200, content=json.dumps(payload))
                self.assert_error(502)
                self.assertFalse(routing._lock.locked())
        self.clock.return_value += 1
        self.get.return_value = httpx.Response(200, content=b"not-json")
        self.assert_error(502)

    def test_provider_geometry_uses_world_bounds_and_accepts_zero_metrics(self):
        coordinates = [[-180, -90], [180, 90]]
        self.get.return_value = httpx.Response(200, json=provider_payload(
            geometry={"type": "LineString", "coordinates": coordinates}, distance=0, duration=0,
        ))
        self.assertEqual(routing.driving_route(REQUEST, self.settings), {
            "geometry": {"type": "LineString", "coordinates": coordinates},
            "distance_m": 0, "duration_s": 0,
        })

    def test_public_http_endpoint_in_recommendation_and_monolith(self):
        for service_name in ("recommendation", "monolith"):
            settings = self.settings.model_copy(update={
                "service_name": service_name,
                "secret_key": "test-only-route-signing-key-not-for-production",
            })
            with self.subTest(service_name=service_name), TestClient(create_app(settings)) as client:
                self.clock.return_value += 20
                response = client.post("/api/map/route", json=REQUEST)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), RESULT)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(client.get("/api/map/route").status_code, 405)
                limited = client.post("/api/map/route", json=REQUEST)
                self.assertEqual(limited.status_code, 429)
                self.assertEqual(limited.headers["Retry-After"], "1")
                self.assertNotIn("geometry", limited.json())

    def test_transport_logs_do_not_expose_locations_and_request_tracing_remains(self):
        for name in ("httpx", "httpcore"):
            logger = logging.getLogger(name)
            self.addCleanup(logger.setLevel, logger.level)
            logger.setLevel(logging.DEBUG)
        app = create_app(self.settings)
        for name in ("httpx", "httpcore"):
            self.assertFalse(logging.getLogger(name).isEnabledFor(logging.INFO))
        with TestClient(app) as client, self.assertLogs("uvicorn.error", level="INFO") as logs:
            response = client.post("/api/map/route", json=REQUEST)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("method=POST status=200" in entry for entry in logs.output))
        self.assertNotIn("11.51,3.86", "\n".join(logs.output))

    def test_http_invalid_input_including_non_finite_json_is_422_not_500(self):
        invalid = (
            {}, {**REQUEST, "origin": {"lat": 3.86, "lng": "11.51"}},
            {**REQUEST, "destination": {"lat": 14, "lng": 12}},
            {**REQUEST, "origin": {"lat": float("nan"), "lng": 12}},
            {**REQUEST, "destination": {"lat": 4, "lng": float("inf")}},
            float("nan"), {"origin": float("inf"), "destination": REQUEST["destination"]},
        )
        for service_name in ("recommendation", "monolith"):
            settings = self.settings.model_copy(update={
                "service_name": service_name,
                "secret_key": "test-only-route-signing-key-not-for-production",
            })
            with TestClient(create_app(settings), raise_server_exceptions=False) as client:
                for payload in invalid:
                    with self.subTest(service_name=service_name, payload=payload):
                        response = client.post(
                            "/api/map/route", content=json.dumps(payload),
                            headers={"Content-Type": "application/json"},
                        )
                        self.assertEqual(response.status_code, 422, response.text)
                        self.assertNotIn("geometry", response.json())
                for raw in ('{"origin":{"lat":1e309,"lng":12},"destination":{"lat":4,"lng":12}}', "{", ""):
                    response = client.post(
                        "/api/map/route", content=raw, headers={"Content-Type": "application/json"},
                    )
                    self.assertEqual(response.status_code, 422, response.text)
        self.get.assert_not_called()

    def test_http_provider_errors_have_no_success_shaped_fallback(self):
        failures = (
            (httpx.Response(400, json={"code": "NoSegment"}), 404),
            (httpx.Response(429), 429),
            (httpx.Response(200, content=b"not-json"), 502),
            (httpx.ReadTimeout("Timeout"), 503),
        )
        with TestClient(create_app(self.settings)) as client:
            for failure, status in failures:
                with self.subTest(status=status):
                    self.clock.return_value += 20
                    self.get.side_effect = failure if isinstance(failure, Exception) else None
                    if isinstance(failure, httpx.Response):
                        self.get.return_value = failure
                    response = client.post("/api/map/route", json=REQUEST)
                    self.assertEqual(response.status_code, status, response.text)
                    self.assertIn("detail", response.json())
                    self.assertNotIn("geometry", response.json())
                    if status == 429:
                        self.assertEqual(response.headers["Retry-After"], "10")


class GatewayRoutingTests(unittest.TestCase):
    def test_gateway_forwards_post_body_and_retry_after_to_recommendation(self):
        settings = Settings(service_name="gateway", _env_file=None)
        app = create_app(settings)
        with TestClient(app) as client:
            upstream = AsyncMock()
            app.state.http_client = upstream
            for status, payload, headers in (
                (200, RESULT, {}),
                (429, {"detail": "Please wait before requesting another road route."}, {"Retry-After": "10"}),
            ):
                with self.subTest(status=status):
                    upstream.request.return_value = httpx.Response(status, json=payload, headers=headers)
                    response = client.post("/api/map/route", json=REQUEST)
                    self.assertEqual(response.status_code, status, response.text)
                    self.assertEqual(response.json(), payload)
                    call = upstream.request.call_args
                    self.assertEqual(call.args, (
                        "POST", f"{settings.recommendation_service_url}/api/map/route",
                    ))
                    self.assertEqual(json.loads(call.kwargs["content"]), REQUEST)
                    self.assertEqual(call.kwargs["params"], [])
                    if status == 429:
                        self.assertEqual(response.headers["Retry-After"], "10")

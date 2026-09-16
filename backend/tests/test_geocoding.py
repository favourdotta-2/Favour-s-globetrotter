import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.application import create_app
from app.core.config import BACKEND_DIR, Settings
from app.services import geocoding_service as geo


def place(**changes):
    return {
        "osm_id": 1234, "osm_type": "node", "name": "Kribi",
        "display_name": "Kribi, Ocean, South, Cameroon",
        "lat": "2.94", "lon": "9.91", "address": {"country_code": "cm"},
        **changes,
    }


class GeocodingTests(unittest.TestCase):
    def setUp(self):
        geo._cache.clear()
        geo._next_request_at = 0
        self.addCleanup(geo._cache.clear)
        self.clock = self.enterContext(patch.object(geo, "monotonic", return_value=100.0))
        self.get = self.enterContext(patch.object(geo.httpx, "get"))
        self.get.return_value = httpx.Response(200, json=[place()])
        directory = self.enterContext(TemporaryDirectory())
        self.settings = Settings(
            service_name="recommendation", data_dir=Path(directory),
            catalog_path=BACKEND_DIR / "data" / "destinations.json", _env_file=None,
        )

    def test_search_contract_country_filter_and_provider_parameters(self):
        self.get.return_value = httpx.Response(200, json=[
            place(address={"country_code": "ng"}), place(), place(),
        ])
        result = geo.search_cameroon("  Kribi   Cameroon ", self.settings)
        self.assertEqual(result, [{
            "id": "osm-node-1234", "name": "Kribi", "display_name": "Kribi, Ocean, South, Cameroon",
            "lat": 2.94, "lng": 9.91, "source": "openstreetmap",
        }])
        args = self.get.call_args.kwargs
        self.assertEqual(args["params"]["q"], "Kribi Cameroon")
        self.assertEqual(args["params"]["countrycodes"], "cm")
        self.assertEqual(args["params"]["limit"], 10)
        self.assertEqual(args["params"]["addressdetails"], 1)
        self.assertEqual(args["headers"]["User-Agent"], self.settings.geocoding_user_agent)
        self.assertEqual(args["timeout"], self.settings.request_timeout_seconds)

    def test_rate_limit_cache_hits_and_cache_copy(self):
        first = geo.search_cameroon("Kribi", self.settings)
        first[0]["name"] = "Changed by caller"
        self.assertEqual(geo.search_cameroon(" kribi ", self.settings)[0]["name"], "Kribi")
        with self.assertRaises(HTTPException) as error:
            geo.search_cameroon("Limbe", self.settings)
        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(error.exception.headers["Retry-After"], "1")
        self.get.assert_called_once()
        self.clock.return_value = 101.0
        geo.search_cameroon("Limbe", self.settings)
        self.assertEqual(self.get.call_count, 2)

    def test_cache_expiration_capacity_and_empty_results(self):
        self.get.return_value = httpx.Response(200, json=[])
        self.assertEqual(geo.search_cameroon("Unknown place", self.settings), [])
        self.assertEqual(geo.search_cameroon("Unknown place", self.settings), [])
        self.get.assert_called_once()
        self.clock.return_value = 100.0 + geo.CACHE_TTL_SECONDS
        geo.search_cameroon("Unknown place", self.settings)
        self.assertEqual(self.get.call_count, 2)
        with patch.object(geo, "CACHE_CAPACITY", 2):
            for index, name in enumerate(("Limbe", "Kribi", "Douala")):
                self.clock.return_value += 1
                geo.search_cameroon(name, self.settings)
                self.assertLessEqual(len(geo._cache), 2)
        self.assertNotIn((self.settings.geocoding_url, "limbe"), geo._cache)

    def test_concurrent_search_is_rejected_without_provider_request(self):
        with geo._lock:
            with self.assertRaises(HTTPException) as error:
                geo.search_cameroon("Kribi", self.settings)
        self.assertEqual(error.exception.status_code, 429)
        self.get.assert_not_called()

    def test_provider_failures_are_not_empty_successes_or_cached(self):
        failures = (
            (httpx.ConnectError("Offline"), 503),
            (httpx.Response(503), 503),
            (httpx.Response(429), 429),
            (httpx.Response(200, content=b"not-json"), 502),
        )
        for response, status in failures:
            with self.subTest(status=status, response=response):
                self.clock.return_value += 20
                self.get.side_effect = response if isinstance(response, Exception) else None
                if isinstance(response, httpx.Response):
                    self.get.return_value = response
                with self.assertRaises(HTTPException) as error:
                    geo.search_cameroon("Kribi", self.settings)
                self.assertEqual(error.exception.status_code, status)
                self.assertEqual(len(geo._cache), 0)

    def test_invalid_provider_records_are_rejected(self):
        invalid = (
            {}, [None], [place(address={})], [place(lat="nan")], [place(lon="inf")],
            [place(lat="90")], [place(lon="-100")], [place(lat=None)],
            [place(osm_id=True)], [place(osm_type=[])], [place(display_name="")],
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                self.clock.return_value += 1
                self.get.return_value = httpx.Response(200, json=payload)
                with self.assertRaises(HTTPException) as error:
                    geo.search_cameroon("Kribi", self.settings)
                self.assertEqual(error.exception.status_code, 502)

    def test_result_limit_and_name_fallback(self):
        self.get.return_value = httpx.Response(200, json=[place(osm_id=index, name=None) for index in range(1, 20)])
        results = geo.search_cameroon("Kribi", self.settings)
        self.assertEqual(len(results), 10)
        self.assertEqual(results[0]["name"], "Kribi")

    def test_http_route_validation_and_search_without_login(self):
        with TestClient(create_app(self.settings)) as client:
            for query in ("", "ab", "   ", "x" * 121):
                self.assertEqual(client.get("/api/map/search", params={"q": query}).status_code, 422)
            self.get.assert_not_called()
            response = client.get("/api/map/search", params={"q": "Kribi"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()[0]["source"], "openstreetmap")

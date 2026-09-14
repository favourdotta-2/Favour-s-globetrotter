import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
import jwt
from fastapi.testclient import TestClient

from app.application import create_app
from app.core.config import BACKEND_DIR, Settings
from app.repositories.json_store import JsonStore, StorageError

TEST_KEY = "test-only-signing-key-not-for-production-1234567890"


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(TemporaryDirectory())
        self.settings = Settings(
            service_name="monolith", secret_key=TEST_KEY, data_dir=Path(self.directory),
            catalog_path=BACKEND_DIR / "data" / "destinations.json", _env_file=None,
        )
        self.client = self.enterContext(TestClient(create_app(self.settings)))
        self.store = JsonStore(self.settings.data_dir, self.settings.catalog_path)

    def signup(self, username="alice"):
        response = self.client.post("/api/auth/signup", json={
            "username": username, "password": "test-password", "preferences": ["nature"],
        })
        self.assertEqual(response.status_code, 201, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def trip(self, headers, **fields):
        return self.client.post("/api/itineraries", headers=headers, json={
            "title": "Nature weekend", "destination_ids": ["ekom-nkam"],
            "start_date": "2026-10-01", "end_date": "2026-10-03", **fields,
        })

    def test_health_catalogue_filters_and_legacy_routes(self):
        self.assertEqual(self.client.get("/ready").status_code, 200)
        records = self.client.get("/destinations?tag=nature").json()
        self.assertGreater(len(records), 0)
        self.assertTrue(all("nature" in row["tags"] for row in records))
        self.assertEqual(self.client.get("/api/destinations?q=does-not-exist").json(), [])
        self.assertEqual(self.client.get("/api/destinations?max_cost=-1").status_code, 422)
        self.assertEqual(self.client.get("/api/destinations?continent=Europe").json(), [])
        self.assertEqual(self.client.get("/api/map/locations").status_code, 200)
        self.assertEqual(self.client.post("/register", json={
            "username": "legacy", "password": "test-password"
        }).status_code, 201)
        self.assertEqual(self.client.post("/login", json={
            "username": "legacy", "password": "test-password"
        }).status_code, 200)

    def test_signup_login_validation_and_private_profile(self):
        headers = self.signup("Alice")
        response = self.client.get("/api/profile", headers=headers)
        self.assertEqual(response.json()["username"], "alice")
        self.assertNotIn("password_hash", response.json())
        user = self.store.read("users")[0]
        self.assertNotEqual(user["password_hash"], "test-password")
        self.assertEqual(self.client.post("/api/auth/signup", json={
            "username": "alice", "password": "another-password",
        }).status_code, 409)
        for username in ("   ", "ab", "user with spaces"):
            self.assertEqual(self.client.post("/api/auth/signup", json={
                "username": username, "password": "test-password",
            }).status_code, 422)
        self.assertEqual(self.client.post("/api/auth/login", json={
            "username": "alice", "password": "incorrect",
        }).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={
            "username": "ALICE", "password": "test-password",
        }).status_code, 200)
        self.assertEqual(self.client.get("/api/profile").status_code, 401)
        self.assertEqual(self.client.get("/api/profile", headers={
            "Authorization": "Bearer invalid"
        }).status_code, 401)
        expired = jwt.encode({"sub": "alice", "iat": 1, "exp": 2}, TEST_KEY, algorithm="HS256")
        self.assertEqual(self.client.get("/api/profile", headers={
            "Authorization": f"Bearer {expired}"
        }).status_code, 401)

    def test_profile_updates_drive_recommendations_and_persist(self):
        headers = self.signup()
        updated = self.client.put("/api/profile", headers=headers, json={
            "full_name": " Alice Traveler ", "preferences": [" ADVENTURE "],
            "bio": " Weekend explorer ", "home_city": " Yaounde ",
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["full_name"], "Alice Traveler")
        self.assertEqual(updated.json()["preferences"], ["adventure"])
        results = self.client.get("/api/recommendations?limit=1", headers=headers)
        self.assertEqual(results.status_code, 200, results.text)
        self.assertEqual(results.json()[0]["id"], "ekom-nkam")
        self.assertGreater(results.json()[0]["match_score"], 0)
        self.assertEqual(self.client.get("/api/recommendations?limit=-2", headers=headers).status_code, 422)
        second_app = self.enterContext(TestClient(create_app(self.settings)))
        self.assertEqual(second_app.get("/api/profile", headers=headers).json()["bio"], "Weekend explorer")

    def test_itinerary_crud_ownership_and_validation(self):
        alice, bob = self.signup("alice"), self.signup("bob")
        created = self.trip(alice)
        self.assertEqual(created.status_code, 201, created.text)
        itinerary_id = created.json()["id"]
        self.assertEqual(created.json()["destinations"][0]["id"], "ekom-nkam")
        self.assertEqual(self.client.get("/api/itineraries", headers=bob).json(), [])
        self.assertEqual(self.client.delete(f"/api/itineraries/{itinerary_id}", headers=bob).status_code, 404)
        changes = {"title": "Updated trip", "destination_ids": ["bamun-palace"], "notes": "New plan"}
        self.assertEqual(self.client.put(
            f"/api/itineraries/{itinerary_id}", headers=bob, json=changes
        ).status_code, 404)
        response = self.client.put(f"/api/itineraries/{itinerary_id}", headers=alice, json=changes)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["destinations"][0]["id"], "bamun-palace")
        for fields in (
            {"title": "  "}, {"destination_ids": []}, {"destination_ids": ["unknown"]},
            {"destination_ids": ["ekom-nkam", "ekom-nkam"]},
            {"end_date": "2026-09-01"}, {"end_date": None}, {"start_date": "bad-date"},
        ):
            self.assertEqual(self.trip(alice, **fields).status_code, 422, fields)
        self.assertEqual(self.client.delete(f"/api/itineraries/{itinerary_id}", headers=alice).status_code, 204)
        self.assertEqual(self.client.get("/api/itineraries", headers=alice).json(), [])

    def test_recommendations_use_past_trips_and_aggregate_popularity(self):
        alice, bob = self.signup("alice"), self.signup("bob")
        self.client.put("/api/profile", headers=alice, json={"preferences": []})
        self.trip(bob, destination_ids=["bamun-palace"])
        recommended = self.client.get("/api/recommendations?limit=1", headers=alice).json()
        self.assertEqual(recommended[0]["id"], "bamun-palace")
        self.assertEqual(self.client.get(
            "/api/itineraries/popularity", headers=alice
        ).json(), {"bamun-palace": 1})
        self.trip(alice, start_date="2000-01-01", end_date="2000-01-03")
        recommended = self.client.get("/api/recommendations?limit=1", headers=alice).json()
        self.assertEqual(recommended[0]["id"], "ekom-nkam")
        self.assertGreater(recommended[0]["match_score"], 1)

    def test_sharing_is_opt_in_revocable_and_hides_owner(self):
        alice, bob = self.signup("alice"), self.signup("bob")
        itinerary_id = self.trip(alice).json()["id"]
        path = f"/api/itineraries/{itinerary_id}/share"
        self.assertEqual(self.client.post(path, headers=bob).status_code, 404)
        share_id = self.client.post(path, headers=alice).json()["share_id"]
        shared_path = f"/api/shared/itineraries/{share_id}"
        shared = self.client.get(shared_path)
        self.assertEqual(shared.status_code, 200)
        self.assertNotIn("username", shared.json())
        self.assertNotIn("id", shared.json())
        self.assertEqual(self.client.post(path, headers=alice).json()["share_id"], share_id)
        self.assertEqual(self.client.delete(path, headers=alice).status_code, 204)
        self.assertEqual(self.client.get(shared_path).status_code, 404)
        self.assertNotEqual(self.client.post(path, headers=alice).json()["share_id"], share_id)

    def test_chat_is_authenticated_shared_validated_and_persistent(self):
        alice, bob = self.signup("alice"), self.signup("bob")
        self.assertEqual(self.client.get("/api/chat/messages").status_code, 401)
        self.assertEqual(self.client.post("/api/chat/messages", headers=alice, json={"text": "   "}).status_code, 422)
        response = self.client.post("/api/chat/messages", headers=alice, json={"text": " Hello travelers! "})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["text"], "Hello travelers!")
        self.assertEqual(self.client.get("/api/chat/messages", headers=bob).json()[0]["username"], "alice")
        self.assertEqual(JsonStore(Path(self.directory)).read("chat_messages")[0]["text"], "Hello travelers!")

    def test_corrupt_storage_surfaces_error_without_overwriting(self):
        self.signup()
        path = Path(self.directory) / "users.json"
        path.write_text("not-json", encoding="utf-8")
        with self.assertLogs("uvicorn.error", level="ERROR"):
            response = self.client.post("/api/auth/signup", json={
                "username": "second", "password": "test-password",
            })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(path.read_text(encoding="utf-8"), "not-json")
        with self.assertRaises(StorageError):
            self.store.read("users")

    def test_concurrent_writes_across_store_instances_are_not_lost(self):
        def append(index):
            store = JsonStore(Path(self.directory))
            store.append("chat_messages", {"id": str(index), "text": f"Message {index}"})

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(append, range(40)))
        self.assertEqual(len(self.store.read("chat_messages")), 40)
        self.assertEqual(len({row["id"] for row in self.store.read("chat_messages")}), 40)

    def test_duplicate_registration_is_atomic(self):
        from app.models.schemas import UserCreate
        from app.services.auth_service import signup
        from fastapi import HTTPException

        def register(_):
            try:
                signup(UserCreate(username="alice", password="test-password"), self.store, self.settings)
                return 201
            except HTTPException as exc:
                return exc.status_code

        with ThreadPoolExecutor(max_workers=4) as executor:
            outcomes = list(executor.map(register, range(4)))
        self.assertEqual(sorted(outcomes), [201, 409, 409, 409])
        self.assertEqual(len(self.store.read("users")), 1)


class MicroserviceTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(TemporaryDirectory())
        self.clients = {}
        for service_name in ("user", "itinerary", "recommendation", "chat", "gateway"):
            settings = Settings(
                service_name=service_name, secret_key=TEST_KEY if service_name == "user" else None,
                data_dir=Path(self.directory) / service_name, _env_file=None,
            )
            self.clients[service_name] = self.enterContext(TestClient(create_app(settings)))

        def get(url, headers, timeout):
            request = httpx.URL(url)
            return self.clients[request.host].get(request.raw_path.decode(), headers=headers)

        self.enterContext(patch("app.core.service_client.httpx.get", side_effect=get))

    def test_independent_services_communicate_without_sharing_files(self):
        response = self.clients["user"].post("/api/auth/signup", json={
            "username": "alice", "password": "test-password", "preferences": ["nature"],
        })
        self.assertEqual(response.status_code, 201, response.text)
        headers = {"Authorization": f"Bearer {response.json()['token']}"}
        created = self.clients["itinerary"].post("/api/itineraries", headers=headers, json={
            "title": "Service trip", "destination_ids": ["ekom-nkam"],
        })
        self.assertEqual(created.status_code, 201, created.text)
        recommended = self.clients["recommendation"].get("/api/recommendations", headers=headers)
        self.assertEqual(recommended.status_code, 200, recommended.text)
        self.assertEqual(recommended.json()[0]["id"], "ekom-nkam")
        self.assertEqual(self.clients["chat"].post(
            "/api/chat/messages", headers=headers, json={"text": "Shared tip"}
        ).status_code, 201)
        self.assertTrue((Path(self.directory) / "user" / "users.json").exists())
        self.assertFalse((Path(self.directory) / "itinerary" / "users.json").exists())
        self.assertFalse((Path(self.directory) / "chat" / "users.json").exists())
        self.assertEqual(self.clients["user"].get("/api/destinations").status_code, 404)
        self.assertEqual(self.clients["gateway"].get("/ready").status_code, 200)

    def test_service_outage_returns_explicit_failure(self):
        with patch("app.core.service_client.httpx.get", side_effect=httpx.ConnectError("offline")):
            response = self.clients["chat"].get(
                "/api/chat/messages", headers={"Authorization": "Bearer anything"}
            )
        self.assertEqual(response.status_code, 503)

    def test_gateway_preserves_method_query_auth_body_and_errors(self):
        requests = []

        async def send(method, url, **kwargs):
            requests.append((method, url, kwargs))
            return httpx.Response(409, json={"detail": "Username already exists"})

        gateway = self.clients["gateway"]
        with patch.object(gateway.app.state.http_client, "request", side_effect=send):
            response = gateway.post(
                "/api/auth/signup?source=demo&source=repeat",
                json={"username": "alice"}, headers={"Authorization": "Bearer example"},
            )
            alias = gateway.post("/register", json={"username": "alice"})
            self.assertEqual(alias.status_code, 409)
        method, url, arguments = requests[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "http://user:8000/api/auth/signup")
        self.assertEqual(arguments["headers"]["authorization"], "Bearer example")
        self.assertEqual(arguments["params"], [("source", "demo"), ("source", "repeat")])
        self.assertEqual(json.loads(arguments["content"]), {"username": "alice"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Username already exists")
        self.assertEqual(gateway.get("/api/not-an-endpoint").status_code, 404)
        with patch.object(gateway.app.state.http_client, "request", side_effect=httpx.ConnectError("offline")):
            self.assertEqual(gateway.get("/api/destinations").status_code, 503)


if __name__ == "__main__":
    unittest.main()

import io
import unittest
from pathlib import Path
from unittest.mock import patch

import av
from fastapi.testclient import TestClient
from PIL import Image

import test_app
from app.application import create_app
from app.core.body_limit import MAX_FILE_BYTES, MAX_REQUEST_BYTES
from app.repositories.json_store import StorageError


def png_bytes(color="green") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(output, format="PNG")
    return output.getvalue()


def mp4_bytes() -> bytes:
    output = io.BytesIO()
    with av.open(output, mode="w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=1)
        stream.width, stream.height, stream.pix_fmt = 16, 16, "yuv420p"
        for packet in stream.encode(av.VideoFrame.from_image(Image.new("RGB", (16, 16), "red"))):
            container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return output.getvalue()


class SocialMediaTests(unittest.TestCase):
    setUp = test_app.ApiTests.setUp
    signup = test_app.ApiTests.signup

    def test_destination_detail_and_one_rating_per_traveler(self):
        alice, bob = self.signup("alice"), self.signup("bob")
        path = "/api/destinations/ekom-nkam"
        initial = self.client.get(path)
        self.assertEqual(initial.status_code, 200)
        self.assertIsNone(initial.json()["rating_average"])
        self.assertEqual(initial.json()["reviews"], [])
        for headers, rating in ((alice, 2), (bob, 4)):
            response = self.client.put(path + "/review", headers=headers, json={
                "rating": rating, "comment": " A memorable waterfall visit. ",
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["comment"], "A memorable waterfall visit.")
            self.assertNotIn("password_hash", response.json()["author"])
        summary = self.client.get(path).json()
        self.assertEqual(summary["review_count"], 2)
        self.assertEqual(summary["rating_average"], 3)
        self.client.put(path + "/review", headers=alice, json={"rating": 5, "comment": "Updated thoughts"})
        summary = self.client.get(path).json()
        self.assertEqual(summary["review_count"], 2)
        self.assertEqual(summary["rating_average"], 4.5)
        self.assertEqual(self.client.get(path + "/review", headers=alice).json()["rating"], 5)
        self.assertEqual(self.client.delete(path + "/review", headers=alice).status_code, 204)
        self.assertEqual(self.client.get(path).json()["rating_average"], 4)
        self.assertEqual(self.client.delete(path + "/review", headers=alice).status_code, 404)
        self.assertEqual(self.client.get("/api/destinations/not-a-place").status_code, 404)

    def test_review_validation_ownership_and_authentication(self):
        headers = self.signup()
        path = "/api/destinations/ekom-nkam/review"
        for rating in (0, 6, 3.5, True, "5"):
            self.assertEqual(self.client.put(path, headers=headers, json={
                "rating": rating, "comment": "A place to visit",
            }).status_code, 422)
        for comment in (" ", "x" * 2001):
            self.assertEqual(self.client.put(path, headers=headers, json={
                "rating": 5, "comment": comment,
            }).status_code, 422)
        self.assertEqual(self.client.put(path, json={"rating": 5, "comment": "hi"}).status_code, 401)
        self.assertEqual(self.client.delete(path).status_code, 401)
        self.assertEqual(self.client.get(path).status_code, 401)

    def test_profile_rating_upsert_is_separate_from_place_ratings(self):
        headers = self.signup()
        path = "/api/profile/app-rating"
        self.assertIsNone(self.client.get(path, headers=headers).json())
        for rating in (5, 3):
            response = self.client.put(path, headers=headers, json={"rating": rating, "comment": "Useful app"})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(path, headers=headers).json()["rating"], 3)
        self.assertEqual(len(self.store.read("app_ratings")), 1)
        self.assertEqual(self.store.read("reviews"), [])
        self.assertEqual(self.client.put(path, headers=headers, json={"rating": 7}).status_code, 422)
        self.assertEqual(self.client.get(path).status_code, 401)

    def test_profile_photo_updates_existing_chat_and_review_authors(self):
        headers = self.signup()
        self.client.post("/api/chat/messages", headers=headers, json={"text": "Before my new photo"})
        self.client.put("/api/destinations/ekom-nkam/review", headers=headers, json={"rating": 5, "comment": "Loved it!"})
        response = self.client.post("/api/profile/avatar", headers=headers, files={
            "file": ("photo.png", png_bytes(), "image/png"),
        })
        self.assertEqual(response.status_code, 200, response.text)
        url = response.json()["avatar_url"]
        image_response = self.client.get(url)
        self.assertEqual(image_response.status_code, 200)
        image = Image.open(io.BytesIO(image_response.content))
        self.assertEqual(image.size, (512, 512))
        self.assertEqual(image.format, "WEBP")
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).json()["avatar_url"], url)
        self.assertEqual(self.client.get("/api/chat/messages", headers=headers).json()[0]["author"]["avatar_url"], url)
        self.assertEqual(self.client.get("/api/destinations/ekom-nkam").json()["reviews"][0]["author"]["avatar_url"], url)
        public = self.client.get("/api/profile/public?usernames=alice").json()["alice"]
        self.assertEqual(set(public), {"username", "full_name", "avatar_url"})
        second = self.client.post("/api/profile/avatar", headers=headers, files={
            "file": ("new.png", png_bytes("blue"), "image/png"),
        })
        self.assertNotEqual(second.json()["avatar_url"], url)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(len(list((Path(self.directory) / "uploads" / "avatars").glob("*"))), 1)
        self.assertEqual(self.client.post("/api/profile/avatar", files={
            "file": ("photo.png", png_bytes(), "image/png")
        }).status_code, 401)

    def test_strict_five_megabyte_boundary_and_gateway_envelope(self):
        headers = self.signup()
        content = png_bytes()
        below = content + b"\x00" * (MAX_FILE_BYTES - 1 - len(content))
        accepted = self.client.post("/api/chat/media", headers=headers, files={
            "file": ("large.png", below, "image/png"),
        })
        self.assertEqual(accepted.status_code, 201, accepted.text)
        for size in (MAX_FILE_BYTES, MAX_FILE_BYTES + 1):
            response = self.client.post("/api/chat/media", headers=headers, files={
                "file": ("large.png", below + b"\x00" * (size - len(below)), "image/png"),
            })
            self.assertEqual(response.status_code, 413, response.text)
        response = self.client.post("/api/profile/avatar", headers=headers, files={
            "file": ("large.png", below + b"\x00", "image/png"),
        })
        self.assertEqual(response.status_code, 413)
        self.assertEqual(len(self.store.read("chat_media")), 1)
        too_large = self.client.post("/api/chat/media", headers=headers, content=b"x" * (MAX_REQUEST_BYTES + 1))
        self.assertEqual(too_large.status_code, 413)

    def test_invalid_or_disguised_uploads_rejected(self):
        headers = self.signup()
        for name, content, kind, status in (
            ("empty.png", b"", "image/png", 422),
            ("fake.png", b"<script>alert(1)</script>", "image/png", 422),
            ("photo.svg", b"<svg/>", "image/svg+xml", 415),
            ("wrong.jpg", png_bytes(), "image/jpeg", 415),
            ("fake.mp4", b"not-video", "video/mp4", 415),
            ("audio.txt", b"hello", "text/plain", 415),
        ):
            response = self.client.post("/api/chat/media", headers=headers, files={"file": (name, content, kind)})
            self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(self.store.read("chat_media"), [])

    def test_emoji_sticker_and_legacy_text_messages(self):
        headers = self.signup()
        for payload in (
            {"text": "Hello \U0001f44b \U0001f30d"},
            {"sticker": "adventure"},
            {"sticker": "hello", "text": "Welcome"},
        ):
            response = self.client.post("/api/chat/messages", headers=headers, json=payload)
            self.assertEqual(response.status_code, 201, response.text)
        response = self.client.post("/api/chat/messages", headers=headers, json={"sticker": "unknown"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.post("/api/chat/messages", headers=headers, json={}).status_code, 422)
        self.assertEqual(len(self.client.get("/api/chat/messages", headers=headers).json()), 3)
        self.assertIn("\U0001f44b", self.store.read("chat_messages")[0]["text"])

    def test_photo_media_requires_auth_and_cannot_be_reused_by_others(self):
        alice, bob = self.signup("alice"), self.signup("bob")
        uploaded = self.client.post("/api/chat/media", headers=alice, files={
            "file": ("holiday.png", png_bytes(), "image/png"),
        })
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        media = uploaded.json()
        self.assertEqual(self.client.get(media["url"]).status_code, 401)
        self.assertEqual(self.client.get(media["url"], headers=bob).status_code, 404)
        self.assertEqual(self.client.post("/api/chat/messages", headers=bob, json={
            "media_id": media["id"]
        }).status_code, 404)
        posted = self.client.post("/api/chat/messages", headers=alice, json={
            "media_id": media["id"], "text": "A photo from my trip",
        })
        self.assertEqual(posted.status_code, 201)
        self.assertEqual(posted.json()["media"]["kind"], "image")
        self.assertEqual(self.client.get(media["url"], headers=bob).status_code, 200)
        self.assertEqual(self.client.get("/api/chat/media/not-a-file", headers=alice).status_code, 404)

    def test_video_upload_decoding_range_delivery_and_persistence(self):
        headers = self.signup()
        response = self.client.post("/api/chat/messages/upload", headers=headers, data={"text": "A video"}, files={
            "file": ("trip.mp4", mp4_bytes(), "video/mp4"),
        })
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["media"]["kind"], "video")
        url = response.json()["media"]["url"]
        media = self.client.get(url, headers={**headers, "Range": "bytes=0-99"})
        self.assertEqual(media.status_code, 206, media.text)
        self.assertEqual(len(media.content), 100)
        self.assertTrue(media.headers["content-range"].startswith("bytes 0-99/"))
        with TestClient(create_app(self.settings)) as restarted:
            self.assertEqual(restarted.get(url, headers=headers).status_code, 200)
            self.assertEqual(restarted.get("/api/chat/messages", headers=headers).json()[0]["media"]["url"], url)

    def test_failed_message_write_does_not_leave_orphan_file(self):
        headers = self.signup()
        from app.services.chat_service import create_uploaded_message
        original_append = self.store.append

        def append(collection, record):
            if collection == "chat_messages":
                raise StorageError("Simulated failure")
            return original_append(collection, record)

        with patch.object(self.store, "append", side_effect=append):
            with self.assertRaises(StorageError):
                create_uploaded_message(png_bytes(), "image/png", "test.png", "", {"username": "alice"}, self.store)
        self.assertEqual(self.store.read("chat_media"), [])
        self.assertEqual(list((Path(self.directory) / "uploads" / "chat").glob("*")), [])


class SocialMicroserviceTests(unittest.TestCase):
    setUp = test_app.MicroserviceTests.setUp

    def test_avatar_review_and_media_across_separate_services(self):
        user_client = self.clients["user"]
        response = user_client.post("/api/auth/signup", json={"username": "alice", "password": "test-password"})
        headers = {"Authorization": "Bearer " + response.json()["token"]}
        avatar = user_client.post("/api/profile/avatar", headers=headers, files={
            "file": ("profile.png", png_bytes(), "image/png"),
        }).json()["avatar_url"]
        posted = self.clients["chat"].post("/api/chat/messages/upload", headers=headers, files={
            "file": ("photo.png", png_bytes(), "image/png"),
        })
        self.assertEqual(posted.status_code, 201, posted.text)
        reviewed = self.clients["recommendation"].put("/api/destinations/ekom-nkam/review", headers=headers, json={
            "rating": 4, "comment": "A review across service boundaries",
        })
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(self.clients["recommendation"].get("/api/destinations/ekom-nkam").json()["reviews"][0]["author"]["avatar_url"], avatar)
        self.assertEqual(self.clients["chat"].get("/api/chat/messages", headers=headers).json()[0]["author"]["avatar_url"], avatar)

    def test_gateway_forwards_media_ranges_and_multipart_content(self):
        import httpx
        seen = []

        async def send(method, url, **kwargs):
            seen.append((method, url, kwargs))
            return httpx.Response(206, content=b"video", headers={
                "content-type": "video/mp4", "content-range": "bytes 0-4/100",
                "accept-ranges": "bytes",
            })

        gateway = self.clients["gateway"]
        with patch.object(gateway.app.state.http_client, "request", side_effect=send):
            response = gateway.get("/api/chat/media/example", headers={"Range": "bytes=0-4"})
            upload = gateway.post("/api/profile/avatar", files={"file": ("photo.png", png_bytes(), "image/png")})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["content-range"], "bytes 0-4/100")
        self.assertEqual(response.content, b"video")
        self.assertEqual(seen[0][2]["headers"]["range"], "bytes=0-4")
        self.assertIn("multipart/form-data", seen[1][2]["headers"]["content-type"])
        self.assertIn(png_bytes(), seen[1][2]["content"])


if __name__ == "__main__":
    unittest.main()

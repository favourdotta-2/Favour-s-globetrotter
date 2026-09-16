# GlobeTrotter - Cameroon Travel Assistant

A React + FastAPI implementation of the CS4122 GlobeTrotter capstone, using **JSON files, not a database server**. Discover places in Cameroon, build and share itineraries, explore a geographic map, personalize recommendations, and talk with other travelers.

**Agreed scope:** complete local Docker services. Cloud deployment and autoscaling are deferred, as requested. Containerization is implemented; the full course Phase 3 cloud deliverable is **not** claimed complete.

## Start the application

Requirements: Docker Desktop with the **Linux engine running** and Docker Compose.

From the repository root in PowerShell:

```powershell
# Creates a git-ignored .env with a random signing key; never overwrites an existing one.
.\scripts\Initialize-Local.ps1

docker compose up -d --build
docker compose ps
```

- **Web app:** http://localhost:5173
- **API gateway:** http://localhost:8000
- **Whole-stack readiness:** http://localhost:8000/ready

Choose **Create an account** in the app. There are no built-in passwords or pre-registered demo users. Usernames contain 3-40 letters, digits, underscores, dots, or hyphens; they are stored lowercase. New passwords must contain 8-128 characters.

If an existing `.env` has an empty `SECRET_KEY`, generate a random key and set it before starting. A minimum of 32 characters is required; never commit or share the file. Changing the key invalidates existing login tokens.

Stop without deleting data:

```powershell
docker compose down
```

Named volumes survive container restarts, rebuilds, and normal `down`. Do **not** add `-v` unless intentionally deleting your saved accounts, itineraries, and messages.

## Product features

| Page | Working features |
| --- | --- |
| Login / signup | Password hashing, JWT sessions, persisted login, session-expiry feedback, travel interests |
| Discover | Local image catalogue, text/category/budget filters, personalized recommendations; click a destination photo or title to open its detail page |
| Destination details | Full place photo/description, average star rating, traveler comments, and your editable/deletable review |
| My itineraries | Multi-destination drafts that survive page navigation, ordered stops, optional dates, notes, create/edit/delete |
| Shared itinerary | Explicit opt-in link sharing, public read-only view, revocable links; other users cannot edit your itinerary |
| Explore map | Leaflet 2D OpenStreetMap, catalogue markers, Cameroon-wide search, and driving routes from the user's location |
| My profile | Name, city, bio, interests, profile-photo upload, an app-rating form, and logout |
| Travel lounge | Authenticated community messages, emoji and sticker pickers, photos/videos below 5 MB, and polling every five seconds |

All photography is served from the supplied [images](images/) directory. Vite copies these assets into the production build; Docker preserves the same paths.

**Catalogue limitations:** the destinations are curated examples, not live commercial listings. Coordinates are approximate. Daily budgets are illustrative **USD**, not verified entry fees or booking quotes. Check local prices, routes, opening hours, and access before travel. Map tiles and external place search require internet access and display provider attribution. The geographic markers are not randomly positioned. Search coverage is limited to places indexed by OpenStreetMap; it cannot guarantee that every real-world place is indexed.

Chat shows the latest 100 messages and is REST polling, not WebSockets. Messages and their attachments are visible to every signed-in user. There are no invented online-user counts. Avoid posting private contact information, credentials, or sensitive travel plans. Shared itinerary links reveal the trip's notes and stops to anyone with the link; sharing is disabled until the owner enables it.

### Destination reviews and app feedback

Click photos/titles in Discover, recommendations, saved-trip covers, or the map's local place details to open `#/destination/{id}`. A signed-in traveler can leave one 1-5 star rating with a comment per destination, then update or delete their own review. Ratings must be integers; the displayed average is calculated from actual saved reviews, not seeded numbers. Up to 100 recent comments are shown, while all saved ratings count toward the average. Your own review remains editable even when it falls outside those 100.

The profile's **Rate us** button opens a separate GlobeTrotter feedback form. It stores one editable app rating per account; it does not publish to an external app store.

### Profile photos and chat media

- Use **Update profile image** on your profile. Photos update in your profile and sidebar immediately, and the current author photo is used in chat and reviews, including older posts. Other clients receive current photos when they refresh/poll. Profile changes also notify other tabs using the same browser session.
- Profile photos are visible to other travelers and are served through public, randomly named image URLs. They are decoded, orientation-corrected, cropped to 512x512, and re-encoded to WebP without original metadata.
- Use **Emojis**, **Stickers**, or **Photo or video** in chat. An attachment may be sent by itself or with a caption. The included travel stickers are local SVG illustrations, not an external sticker service.
- Each original file must be **strictly smaller than 5,000,000 bytes** (decimal 5 MB). A file exactly 5 MB is rejected. The browser and backend both enforce this rule; multipart request envelopes are capped separately at 6 MB.
- Photos: JPEG, PNG, WebP, GIF, up to 16 megapixels. Uploaded images are decoded and re-encoded to WebP with a maximum 2048x2048 bounding box. Animated images use the first frame.
- Videos: H.264 MP4 or VP8/VP9 WebM, up to 16 megapixels per frame. File signatures, the actual codec, and a decoded frame are checked with PyAV; filenames and browser MIME declarations alone are not trusted. The video is not transcoded. Use browser-compatible audio codecs for sound.
- Chat files require authentication. Image elements/video players use authenticated fetches and temporary browser blob URLs; bearer tokens are never placed in media URLs. Video loading is user-triggered, with normal playback controls. Blob URLs are revoked when a message view is released.
- JSON files remain the database for accounts, reviews, ratings, messages, and attachment metadata. Binary images/videos are stored alongside them under the owning service's `uploads/` directory, not as base64 strings inside JSON.
- Existing accounts without photos and existing text-only messages continue to work. No reset or manual data migration is required.

### Cameroon map, external search, and driving directions

The map uses the original [Leaflet](https://leafletjs.com/) 2D map and standard [OpenStreetMap tiles](https://operations.osmfoundation.org/policies/tiles/). Drag to pan or use the zoom controls. It no longer requires WebGL, 3D rendering, or a MapLibre worker. Public tiles are for ordinary interactive viewing; no bulk downloads, prefetching, or offline tile packs are implemented. Keep OpenStreetMap attribution visible.

Click a destination marker or its image/name in the map's collection list. On the first selection, read the location-sharing notice and choose **Use my location**, then allow the browser's location prompt. A blue marker shows the detected origin and a blue road-following route leads to the destination, with distance and estimated driving time. Pressing **Enter** in the search field (or clicking **Search Cameroon**) selects the first match and requests the same directions; select another search result to change the target.

Location sharing lasts only for that map visit. **Update route** obtains a fresh position (the browser may reuse a fix up to 60 seconds old); **Stop using my location**, clearing the selection, or leaving the page removes the current route and discards pending results. There is no continuous GPS tracking or automatic rerouting. Geolocation requires **HTTPS or localhost**, device location services, and browser permission. Denied/unavailable/timed-out location, positions outside Cameroon, missing road coverage, throttling, and provider outages show explicit errors, never a made-up straight-line route.

Driving directions use the public [OSRM demo service](https://project-osrm.org/) with OpenStreetMap road data, explicitly selected for this small local demonstration. After permission, origin/destination coordinates are sent to OSRM. GlobeTrotter keeps them only in memory for the current request/view, not in JSON storage or a route cache; the app uses a POST body rather than putting coordinates in its own access-log URLs. OSRM has its own service/privacy policies. The backend conservatively allows at most one outgoing routing request per second across this single local process and rejects concurrent requests with a retry message. There are no automatic provider retries. Routes snap to mapped roads within 1 km of each endpoint; an isolated landmark may have no driving route. Estimates exclude live traffic and are not turn-by-turn navigation or a guarantee of road safety/accessibility. Do not depend on the public demo for production availability.

Map navigation is locked to Cameroon's bounding area (8.3-16.3 degrees east, 1.6-13.2 degrees north). The initial view and **Show Cameroon** button use these same bounds; panning and zooming out cannot move the map away to another part of the world. This is a rectangular navigation restriction, not an exact country-border mask, so neighboring areas may still appear near the edges.

**The public [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/) applies to search.** This provider was explicitly selected for the small local project. The operator is responsible for ongoing compliance. Searches are sent only on form submission, not autocomplete. A single backend search process:

- Sends an identifying User-Agent and requests at most ten results with `countrycodes=cm`.
- Verifies each returned country and finite Cameroon coordinates.
- Shares a bounded, 256-query, 24-hour in-memory cache across users (including empty results).
- Allows no more than one external request per second; concurrent/too-frequent uncached searches receive an explicit retry message.
- Reports provider/network failures rather than pretending there are no matches.

Do not enter personal, private, or confidential information in searches. Only indexed places can be found; alternative spellings or nearby towns may help. Search results outside the curated catalogue can be viewed on the map but cannot be added as invalid catalogue IDs to itineraries. Search and catalogue lists remain available when tiles or geolocation are unavailable.

Keep exactly **one recommendation worker/instance** with the public providers; do not run the monolith and microservices together or scale them independently against these services. A larger deployment needs suitable commercial/self-hosted providers and shared rate limiting. Set `GEOCODING_URL` / `GEOCODING_USER_AGENT` for a Nominatim-compatible search provider and `ROUTING_URL` / `ROUTING_USER_AGENT` for an OSRM-compatible driving provider in the root `.env`, then recreate the recommendation container (or monolith). `ROUTING_URL` includes the `/route/v1/driving` path. Changing provider does not require rebuilding the frontend. The old `VITE_MAP_STYLE_URL` setting is no longer used.

## Architecture

### Phase 1: runnable FastAPI monolith

One FastAPI process hosts all routers and service logic, with JWT authentication and JSON persistence. It uses the same frontend and business logic as the decomposed version.

Stop the normal stack first because the same local ports are used:

```powershell
docker compose down
docker compose -p globetrotter-phase1 -f docker-compose.monolith.yml up -d --build

# Stop Phase 1 when finished
docker compose -p globetrotter-phase1 -f docker-compose.monolith.yml down
```

The Phase 1 deployment has its **own named data volume**. Data is not automatically migrated between the monolith and the microservices.

The six course endpoints are available as aliases:

| Course endpoint | Canonical app endpoint |
| --- | --- |
| `POST /register` | `POST /api/auth/signup` |
| `POST /login` | `POST /api/auth/login` |
| `GET /destinations` | `GET /api/destinations` |
| `GET /recommendations` | `GET /api/recommendations` |
| `POST /itineraries` | `POST /api/itineraries` |
| `GET /itineraries` | `GET /api/itineraries` |

The new itinerary payload uses `destination_ids`, not the old Flask starter's free-text destination names.

### Phase 2: independent services

The default Compose configuration launches **six containers**:

```text
Browser -> React / Nginx :5173 -> FastAPI Gateway :8000
                                      |
                   +------------------+-----------------+
                   |                  |                 |
                User API         Itinerary API     Recommendation API
                   |                  |                 |
               users.json       itineraries.json   destinations.json
                                      |
                                  Chat API -> chat_messages.json

Authenticated services -> User API /auth/me for token validation
Itinerary API -> Recommendation API for the destination catalogue
Recommendation API -> User API + Itinerary API for personalization
```

| Container | Responsibilities | Private data |
| --- | --- | --- |
| `user` | Registration, login, JWT validation, profile/preferences, avatars, app feedback | `users-data` volume |
| `itinerary` | Itinerary CRUD, ownership, sharing, aggregate popularity counts | `itineraries-data` volume |
| `recommendation` | Destination details/search, place reviews, map search/driving routes, recommendation scoring | Catalogue packaged in image; reviews in `recommendations-data` |
| `chat` | Authenticated shared messages and validated media files | `chat-data` volume |
| `gateway` | Request routing, query/body/auth forwarding, explicit upstream timeout/unavailability errors | None |
| `frontend` | Production React bundle and same-origin `/api` proxy | None |

The services run in **separate processes and containers**, not just different Python modules inside one running monolith. They reuse shared source code and a parameterized backend Dockerfile. `SERVICE_NAME` chooses each container's routers. Compose DNS resolves service names; only the frontend and gateway are published on localhost. The JWT signing key is supplied only to the user container. Other services validate sessions by calling the user API, rather than reading its JSON file. A limited public-author lookup returns only username, display name and photo URL, so historical messages/reviews can use up-to-date avatars without exposing private profile fields.

Recommendation ranking:

1. Three points for each matching preference tag/mood.
2. One point for each matching tag from the user's past dated trips.
3. Up to two popularity points from the number of saved itineraries containing a destination.
4. Alphabetical tie-breaking for reproducible results.

Other users' itinerary contents are not exposed by the popularity endpoint, only per-destination counts. Network failures are reported to the UI instead of silently returning empty recommendations.

### Phase 3: containerization completed, cloud work deferred

Implemented: independently packaged containers, local DNS-based discovery, health/readiness checks, persistent volumes, a gateway, and Nginx serving the production frontend.

Not implemented/deployed in the agreed local scope:

- Public-cloud deployment on AWS, GCP, or Azure.
- Kubernetes/Swarm orchestration.
- At least three replicas of each service.
- Cloud load balancing and horizontal autoscaling.
- Production TLS, distributed metrics/tracing, backups, and high availability.

**Do not scale JSON-writing containers across hosts.** File locks and atomic replacement protect local transactions, but do not turn JSON files into a distributed database. Each domain has one owning service and one local volume. The user service and local disk remain single points of failure. Millions of users, global availability, and full Phase 3 resilience are not supported by this setup.

A later cloud phase needs an agreed persistence design (for example, a coordinated single-writer storage service if JSON remains mandatory) and explicit load-balancing, recovery, and scaling work. Phase 4 caching, message queues, and circuit breakers are outside this implementation.

## Source layout

```text
backend/
  app/
    application.py             # Monolith/service application factory
    main.py                    # Uvicorn entry point
    core/                      # Configuration, JWTs, HTTP service client
    models/schemas.py          # Validated API inputs
    repositories/json_store.py # File-locked, atomic JSON transactions
    routers/                   # REST interfaces and API gateway
    services/                  # User, destination, itinerary, profile, chat logic
  data/destinations.json        # Versioned catalogue; mutable files ignored
  tests/                       # Core, social/media, and Cameroon search regressions
  Dockerfile
  requirements.txt
frontend/
  src/
    App.jsx                    # Session, shared draft, navigation
    api.js                     # HTTP errors, sessions, cancellable reads
    components.jsx
    pages/                     # Account, Discover, Destination, Itinerary, Map, Chat
    styles.css
  Dockerfile
  nginx.conf
  package.json
  package-lock.json
images/
scripts/Initialize-Local.ps1
docker-compose.yml
docker-compose.monolith.yml
```

The original root `app/`, `Dockerfile`, and `requirements.txt` are retained as the historical Flask starter. They are **not used** by either current Compose setup; use the frontend/backend instructions here.

## Native development

Python 3.12+ and Node.js 22.12+ are recommended. Backend dependencies also work with the available Python 3.14 environment.

From the root, initialize the secret and virtual environment:

```powershell
.\scripts\Initialize-Local.ps1
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Terminal 1, run the FastAPI monolith from **inside `backend`** so the historical root `app` package does not shadow it:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Native monolith OpenAPI docs: http://localhost:8000/docs. Do not run native servers and Docker simultaneously on the same ports.

### Configuration

| Variable | Default / requirement |
| --- | --- |
| `SERVICE_NAME` | `monolith`; Compose builds `user`, `itinerary`, `recommendation`, `chat`, `gateway` variants |
| `SECRET_KEY` | Required for user/monolith; random, at least 32 characters |
| `FRONTEND_ORIGIN` | `http://localhost:5173` |
| `DATA_DIR` | Native: `backend/data`; Docker: `/var/lib/globetrotter` |
| `CATALOG_PATH` | Versioned `backend/data/destinations.json`; Docker: `/app/data/destinations.json` |
| `USER_SERVICE_URL` | `http://user:8000` |
| `ITINERARY_SERVICE_URL` | `http://itinerary:8000` |
| `RECOMMENDATION_SERVICE_URL` | `http://recommendation:8000` |
| `CHAT_SERVICE_URL` | `http://chat:8000` |
| `REQUEST_TIMEOUT_SECONDS` | 5 |
| `GEOCODING_URL` | `https://nominatim.openstreetmap.org/search`; server-side Cameroon place search |
| `GEOCODING_USER_AGENT` | Identifies this application to the geocoding provider; set an appropriate contact identifier before public deployment |
| `VITE_API_BASE_URL` | `/api`; build-time only, normally leave unset |

Root `.env` and optional `backend/.env` are loaded for native development; process environment overrides files. Never put secrets into frontend environment variables or a Docker build argument.

## API reference

Protected requests use `Authorization: Bearer <token>`. Tokens expire after 24 hours. Logout clears the browser session; it does not revoke previously copied tokens. The local demo stores its token in localStorage, so production hardening should revisit session storage, HTTPS, rate limiting, and moderation before public deployment.

| Method | Canonical path | Access |
| --- | --- | --- |
| POST | `/api/auth/signup`, `/api/auth/login` | Public |
| GET | `/api/auth/me`, `/api/profile` | Signed in |
| PUT | `/api/profile` | Current user |
| POST | `/api/profile/avatar` | Current user; multipart `file` |
| GET | `/api/profile/avatars/{filename}` | Public profile photo |
| GET | `/api/profile/public?usernames=alice,bob` | Public author names/photo URLs only, at most 100 usernames |
| GET, PUT | `/api/profile/app-rating` | Current user's app feedback |
| GET | `/api/destinations?q=&tag=&mood=&max_cost=&continent=` | Public |
| GET | `/api/recommendations?limit=6` | Signed in |
| GET | `/api/map/locations` | Public |
| GET | `/api/map/search?q=Kribi` | Public; Cameroon-only external search |
| POST | `/api/map/route` | Public; `{origin: {lat, lng}, destination: {lat, lng}}` within Cameroon; returns GeoJSON LineString `geometry`, `distance_m`, `duration_s` |
| GET | `/api/destinations/{id}` | Public destination details, rating summary, recent reviews |
| GET, PUT, DELETE | `/api/destinations/{id}/review` | Current user's own place review |
| GET, POST | `/api/itineraries` | Current user's trips |
| PUT, DELETE | `/api/itineraries/{id}` | Owner only |
| POST, DELETE | `/api/itineraries/{id}/share` | Owner only |
| GET | `/api/shared/itineraries/{share_id}` | Public with active link |
| GET | `/api/itineraries/popularity` | Signed in; aggregate counts only |
| GET, POST | `/api/chat/messages` | Signed in |
| POST | `/api/chat/messages/upload` | Signed in; multipart `file` and optional `text`, publishes an attachment message |
| POST | `/api/chat/media` | Signed in; standalone upload, private until linked to an owner's message |
| GET | `/api/chat/media/{id}` | Uploader, or any signed-in user after the attachment is posted; supports byte ranges |
| GET | `/health`, `/ready` | Operations |

Example itinerary body:

```json
{
  "title": "A Cameroon weekend",
  "destination_ids": ["ekom-nkam", "bamun-palace"],
  "start_date": "2026-10-10",
  "end_date": "2026-10-12",
  "notes": "Confirm local access and transport before leaving."
}
```

Dates must both be supplied or both be empty/null, and end must not precede start. At least one unique, valid destination ID is required. Sharing is off by default and uses a random link token. Owners can revoke links without deleting their trips.

The JSON store holds a cross-process file lock around each read-modify-write operation, flushes and fsyncs a temporary file, and atomically replaces the original. Concurrent registrations are checked under the same lock. Invalid/corrupt JSON produces a visible storage error and is never treated as an empty collection. This is local concurrency protection, not cross-host consensus.

## Validation and operations

Run the focused backend regression tests using Python's standard-library unittest runner (no additional test framework):

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Tests use temporary directories, not real user data. They cover authentication, preferences/recommendations, trip validation/ownership, sharing, chat, corrupt-file handling, concurrent writes/registrations, service calls, and gateway forwarding/failure responses. Social/media regressions also cover real rating averages, review ownership, avatar updates on older content, image decoding, valid MP4 decoding, private-media access, persistence, and the exact 4,999,999 / 5,000,000 / 5,000,001-byte upload boundaries. Geocoding tests mock the external provider and verify Cameroon-only results, malformed coordinates, query validation, rate limiting, cache expiry/capacity, and explicit provider errors; the automated tests do not send requests to Nominatim.

Browser checks cover destination-image navigation, review create/edit/delete, avatar propagation, unsent chat/review drafts surviving cross-tab profile refreshes, app-rating persistence, profile logout, emoji/sticker/photo/video messages, video playback, and exact-5-MB rejection. Map checks cover live Kribi search, camera movement, 2D/3D pitch controls, catalogue links, and usable lists/search without WebGL. The new pages were also checked for horizontal overflow at a 360px mobile viewport.

Frontend production build:

```powershell
cd frontend
npm run build
```

From the root:

```powershell
docker compose config --quiet
docker compose ps
docker compose logs --tail 50 gateway user itinerary recommendation chat
Invoke-RestMethod http://localhost:8000/ready
```

Each API exposes liveness (`/health`) and storage readiness (`/ready`). Gateway readiness checks every upstream. Request logs include service name, a request ID, status, and duration; they do not log auth tokens or message bodies. Do not assume gateway `/docs` aggregates upstream OpenAPI schemas.

For backup, stop writes and back up **all four named volumes**, including each volume's `uploads/` files, plus the signing key securely. Keep a copy before upgrading. Native data and Docker volumes are separate stores. Restore procedures and production-grade backup automation are future work.

### Troubleshooting unavailable storage

`Data storage is unavailable. Please contact the administrator.` means a JSON read, file lock, or write failed. The app deliberately refuses to treat inaccessible data as an empty database. **Do not replace JSON files with `[]`, delete volumes, run a factory reset, or use `docker compose down -v` to clear this error.**

- Check `docker compose ps` and the owning service's logs, for example `docker compose logs --tail 100 user`. A malformed JSON file, permission error, full disk, and read-only filesystem require different repairs.
- If Docker reports `Read-only file system` or `Input/output error`, back up any readable volume data first. Restart Docker Desktop (this briefly interrupts other Docker apps), then run `docker compose up -d --wait` and check `http://localhost:8000/ready`. A normal restart does not delete named volumes. If filesystem errors persist, investigate Docker Desktop/WSL storage rather than overwriting application data.
- Keep Docker Desktop and its engine running while using the Docker setup. If a restart remains stuck at `Starting`, its WSL environment may need to be restarted as well. Check for other running WSL distributions first; a global WSL shutdown interrupts those workloads too.
- Run only one setup on ports 5173 and 8000. On Windows, a native server listening on `0.0.0.0:8000` can coexist with Docker's more-specific `127.0.0.1:8000` listener; Vite's localhost proxy may then reach Docker instead of the native API. Check `Get-NetTCPConnection -State Listen -LocalPort 5173,8000` and identify the owning processes before stopping anything.
- For Docker operation, stop this project's native Vite/Uvicorn servers. For native operation, stop this project's Compose stack with `docker compose stop` first. Native JSON files and Docker-volume accounts are separate; switching modes does not migrate or merge them.

## Course references and design decisions

Primary source supplied by the user: **Engr. Daniel Moune, ICT University, CS4122 Distributed Systems and Cloud Computing, Class 02, July 14, 2026**, file `Class 02 - CS4122 Distributed Systems and Cloud Computing.pdf`. Page references below refer to the **43-page PDF file**, not its embedded slide counter (which uses an 84-slide deck and repeats some slides).

| PDF pages | Topic | Application decision |
| --- | --- | --- |
| 1-4 | Course outline: cloud models, GlobeTrotter capstone, Docker lab | Course-oriented phases and repeatable local startup |
| 27-28 | GlobeTrotter business requirements and four-phase timeline | Destination search, preference/past-trip/popularity recommendations, trip management and sharing |
| 29-30 | Phase 1: monolith, JSON data, JWT, six core REST endpoints | Runnable FastAPI monolith, file persistence, endpoint aliases |
| 31-32 | Phase 2: user, itinerary, recommendation services and API gateway | Independently running services, private data ownership and synchronous HTTP communication |
| 33-34 | Phase 3: Docker, orchestration, load balancing, at least three service instances, autoscaling, cloud hosting | Docker portion implemented; cloud/scaling explicitly deferred at the user's request |
| 33-34 | Phase 4: caching, queues, resilience patterns | Outside agreed scope; no false claim of distributed resilience |
| 35-36 | Architecture sketch and trade-off exercise | Documented JSON constraints, failure behavior, and data ownership |

React UI, the Cameroon photo catalogue, a geographic map, and the community lounge extend the course baseline according to the user's requirements. The lecture's scale and availability requirements are target architecture goals, not achieved guarantees for this local JSON implementation.

### Implementation references

- [React documentation](https://react.dev/learn)
- [Vite: static assets](https://vite.dev/guide/assets.html) and [production builds](https://vite.dev/guide/build.html)
- [FastAPI: multiple-file applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/) and [security](https://fastapi.tiangolo.com/tutorial/security/)
- [Pydantic validation](https://docs.pydantic.dev/latest/concepts/validators/)
- [PyJWT usage](https://pyjwt.readthedocs.io/en/stable/usage.html)
- [Werkzeug password hashing](https://werkzeug.palletsprojects.com/en/stable/utils/#module-werkzeug.security)
- [filelock documentation](https://py-filelock.readthedocs.io/en/latest/) and [HTTPX](https://www.python-httpx.org/)
- [Docker Compose](https://docs.docker.com/compose/) and [volumes](https://docs.docker.com/engine/storage/volumes/)
- [Leaflet reference](https://leafletjs.com/reference.html), [OpenStreetMap attribution](https://www.openstreetmap.org/copyright), [tile usage policy](https://operations.osmfoundation.org/policies/tiles/), [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/), and [OSRM routing API](https://project-osrm.org/docs/v5.24.0/api/#route-service)
- [Pillow image processing](https://pillow.readthedocs.io/) and [PyAV media decoding](https://pyav.org/docs/stable/)

The supplied image files are used locally. Verify image usage rights before publishing the application publicly.

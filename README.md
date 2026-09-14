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
| Discover | Local image catalogue, text/category/budget filters, empty/loading/error states, personalized recommendations |
| My itineraries | Multi-destination drafts that survive page navigation, ordered stops, optional dates, notes, create/edit/delete |
| Shared itinerary | Explicit opt-in link sharing, public read-only view, revocable links; other users cannot edit your itinerary |
| Explore map | Leaflet/OpenStreetMap map, coordinates-based markers, clickable destination list, add-to-itinerary action |
| My profile | Name, city, bio, and interests; preference changes affect recommendations |
| Travel lounge | One authenticated community chat for everyone, persisted messages, automatic polling every five seconds |

All photography is served from the supplied [images](images/) directory. Vite copies these assets into the production build; Docker preserves the same paths.

**Catalogue limitations:** the destinations are curated examples, not live commercial listings. Coordinates are approximate. Daily budgets are illustrative **USD**, not verified entry fees or booking quotes. Check local prices, routes, opening hours, and access before travel. Map tiles require internet access, display OpenStreetMap attribution, and show a warning if loading fails. The geographic markers are not randomly positioned.

Chat shows the latest 100 messages and is REST polling, not WebSockets. Messages are visible to every signed-in user. There are no invented online-user counts. Avoid posting private contact information, credentials, or sensitive travel plans. Shared itinerary links reveal the trip's notes and stops to anyone with the link; sharing is disabled until the owner enables it.

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
| `user` | Registration, login, JWT validation, profile/preferences | `users-data` volume |
| `itinerary` | Itinerary CRUD, ownership, sharing, aggregate popularity counts | `itineraries-data` volume |
| `recommendation` | Read-only destination search, map catalogue, recommendation scoring | Catalogue packaged in image |
| `chat` | Authenticated shared community messages | `chat-data` volume |
| `gateway` | Request routing, query/body/auth forwarding, explicit upstream timeout/unavailability errors | None |
| `frontend` | Production React bundle and same-origin `/api` proxy | None |

The services run in **separate processes and containers**, not just different Python modules inside one running monolith. They reuse shared source code and a parameterized backend Dockerfile. `SERVICE_NAME` chooses each container's routers. Compose DNS resolves service names; only the frontend and gateway are published on localhost. The JWT signing key is supplied only to the user container. Other services validate sessions by calling the user API, rather than reading its JSON file.

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
  tests/test_app.py             # unittest + FastAPI TestClient regressions
  Dockerfile
  requirements.txt
frontend/
  src/
    App.jsx                    # Session, shared draft, navigation
    api.js                     # HTTP errors, sessions, cancellable reads
    components.jsx
    pages/                     # Account, Discover, Itinerary, Map, Chat
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
| `VITE_API_BASE_URL` | `/api`; build-time only, normally leave unset |

Root `.env` and optional `backend/.env` are loaded for native development; process environment overrides files. Never put secrets into frontend environment variables or a Docker build argument.

## API reference

Protected requests use `Authorization: Bearer <token>`. Tokens expire after 24 hours. Logout clears the browser session; it does not revoke previously copied tokens. The local demo stores its token in localStorage, so production hardening should revisit session storage, HTTPS, rate limiting, and moderation before public deployment.

| Method | Canonical path | Access |
| --- | --- | --- |
| POST | `/api/auth/signup`, `/api/auth/login` | Public |
| GET | `/api/auth/me`, `/api/profile` | Signed in |
| PUT | `/api/profile` | Current user |
| GET | `/api/destinations?q=&tag=&mood=&max_cost=&continent=` | Public |
| GET | `/api/recommendations?limit=6` | Signed in |
| GET | `/api/map/locations` | Public |
| GET, POST | `/api/itineraries` | Current user's trips |
| PUT, DELETE | `/api/itineraries/{id}` | Owner only |
| POST, DELETE | `/api/itineraries/{id}/share` | Owner only |
| GET | `/api/shared/itineraries/{share_id}` | Public with active link |
| GET | `/api/itineraries/popularity` | Signed in; aggregate counts only |
| GET, POST | `/api/chat/messages` | Signed in |
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

Tests use temporary directories, not real user data. They cover authentication, preferences/recommendations, trip validation/ownership, revocable sharing, chat, corrupt-file handling, concurrent writes/registrations, independent service calls, and gateway forwarding/failure responses.

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

For backup, stop writes and back up **all three named volumes** plus the signing key securely. Keep a copy before upgrading. Native data and Docker volumes are separate stores. Restore procedures and production-grade backup automation are future work.

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
- [Leaflet reference](https://leafletjs.com/reference.html), [OpenStreetMap attribution](https://www.openstreetmap.org/copyright), and [tile usage policy](https://operations.osmfoundation.org/policies/tiles/)

The supplied image files are used locally. Verify image usage rights before publishing the application publicly.

# SkillSwap (Python full stack)

Peer-to-peer skill barter platform with smart matching. Users list the skills they can teach and want to learn, find partners through a matching algorithm, exchange swap requests, schedule video sessions, rate each other, get ML skill recommendations, and verify their skills with an AI-generated test.

This is the Python version of SkillSwap. The FastAPI backend replaces the earlier Spring Boot backend **and** the separate Python ML service: one Python app now does everything. The API keeps the same URLs and JSON, so the React frontend is unchanged apart from the port it talks to.

| Layer | Technology | Port |
|---|---|---|
| Frontend | React 18 + Vite, React Router, Axios (served by nginx in Docker) | 3000 |
| Backend | FastAPI, SQLAlchemy 2.0 ORM, Pydantic validation, JWT (PyJWT) + bcrypt | 8000 |
| Database | SQLite (one file, no server to install) | |
| ML | scikit-learn model saved with Pickle (AI Picks), Groq LLM (skill test) | inside the backend |
| Deployment | Docker + Docker Compose | |

```
Browser ──> React (Vite) ──REST/Axios──> FastAPI ──SQLAlchemy──> SQLite file
                                            ├──> model.pkl (recommendations, in-process)
                                            └──> Groq API (skill test questions)
```

## Quick start (Docker)

1. Install Docker Desktop.
2. Get a free Groq API key at https://console.groq.com/keys (only needed for the skill test).
3. In this folder:

```bash
cp .env.example .env        # then paste your Groq key into .env
docker compose up --build
```

4. Open http://localhost:3000. Interactive API docs: http://localhost:8000/docs

## Running without Docker (Windows PowerShell shown)

Requirements: Python 3.11+ and Node 18+.

```powershell
# 1. Backend (terminal 1)
cd backend
python -m venv .venv
.venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env             # add GROQ_API_KEY for the skill test
python -m app.ml.train             # optional: trains data/model.pkl (also done automatically on first start)
uvicorn app.main:app --reload --port 8000

# 2. Frontend (terminal 2)
cd frontend
npm install
npm run dev                        # http://localhost:3000, /api is proxied to :8000
```

The database file `backend/data/skillswap.db` is created automatically on first start. Delete it to start fresh.

### Accounts created on first start

| Role | Email | Password |
|---|---|---|
| Admin | admin@skillswap.com | admin123 |
| Demo users | aarav@demo.com, diya@demo.com, kiran@demo.com, meera@demo.com, rohan@demo.com | demo1234 |

Aarav teaches Java and wants Python; Diya teaches Python and wants Java, so matching, requests and sessions can be shown immediately. Set `SEED_DEMO_USERS=false` to skip them.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

14 tests cover registration and login, validation errors, skills, matching scores, search, the full swap → session → rating flow, AI Picks, admin suspend/delete, and the skill test (with a fake question generator, so no API key is needed).

## Project structure

```
skillswap-python/
├── docker-compose.yml, .env.example
├── backend/                         FastAPI
│   ├── app/
│   │   ├── main.py                  App setup: startup (tables, seed, model), CORS, routers
│   │   ├── config.py                Settings from environment variables / .env
│   │   ├── database.py              SQLAlchemy engine, session per request (get_db)
│   │   ├── models.py                Tables: User, Skill, SwapRequest, Session, Rating, skill test tables
│   │   ├── schemas.py               Pydantic request/response models (camelCase JSON)
│   │   ├── security.py              bcrypt, JWT, get_current_user, require_admin
│   │   ├── errors.py                ApiError + handlers -> {"status", "message"}
│   │   ├── seed.py                  Admin + demo users on first start
│   │   ├── routers/api.py           Endpoints: auth, users, skills, swaps, sessions, ratings, admin
│   │   ├── routers/skill_tests.py   Skill test endpoints
│   │   ├── services/core.py         Business rules for accounts, skills, swaps, sessions, ratings, admin
│   │   ├── services/matching.py     Smart matching algorithm and search
│   │   ├── services/recommendations.py  AI Picks (model + fallback)
│   │   ├── services/skill_test.py   Skill test: question bank, scoring, timer, anti-cheating
│   │   └── ml/                      train.py, recommender.py, question_generator.py
│   ├── data/skill_profiles.csv      Training data (420 learner skill profiles)
│   └── tests/                       pytest API tests
└── frontend/                        React + Vite (pages, components, Axios client, AuthContext)
```

## How the main parts work

### Request flow
React calls `/api/...` → Vite (dev) or nginx (Docker) forwards it to FastAPI on port 8000 → the route function runs its **dependencies** first: `get_db` opens a database session and `get_current_user` checks the JWT → the route calls a service function → the service uses SQLAlchemy to read/write SQLite and returns a Pydantic model → FastAPI turns it into camelCase JSON. Any `ApiError` (or validation error) becomes `{"status": 409, "message": "..."}`.

### JWT authentication
Passwords are stored as **bcrypt** hashes. Login checks the hash and returns a token signed with HS256 (24 h). React stores it and Axios sends `Authorization: Bearer <token>`. `get_current_user` decodes it, loads the user, and rejects suspended users even if their token hasn't expired. `require_admin` protects `/api/admin/*`.

### Smart matching (`services/matching.py`)
One query loads every active user's skills with the user (`joinedload`, no N+1). For each other user: +35 if they teach something I want (+3/6/10 for its level, +10 if AI-verified), +35 if they want something I teach, + rating × 2 (max 10), +5 for the same city, capped at 100. Sorted by score, then rating.

### ML recommendations (`ml/train.py`, `ml/recommender.py`)
Item-based collaborative filtering: a profile × skill matrix from 420 profiles, cosine similarity between skills (scikit-learn), saved with Pickle. For a user, it adds the similarity rows of their skills (wanted skills weigh 1.5×), removes skills they already have and returns the top 8, plus up to 3 SkillSwap users who teach each. Unknown names are fuzzy-matched ("reactjs" → React). If the model can't help, it falls back to the most-offered skills.

### AI skill verification test (`services/skill_test.py`)
For a skill the user teaches, the backend keeps a shared question bank per skill and level. Below 30 questions it asks Groq for 10 more, validates each one, and stores them. Ten random questions with shuffled options and a 10-minute server-side timer. ≥ 80% verifies the claimed level, 50–79% one level lower, below 50% fails with a 24-hour cooldown. Correct answers never reach the browser.

### Video calls
Each session gets a unique free Jitsi Meet room (`https://meet.jit.si/SkillSwap-xxxx`).

## Spring Boot → FastAPI: what replaced what

| Spring Boot version | Python version |
|---|---|
| `@RestController` + `@GetMapping` | `APIRouter` + `@router.get` |
| `@Service` classes | functions in `services/` |
| JPA `@Entity` + Hibernate | SQLAlchemy models (`models.py`) |
| `JpaRepository` queries | `select(...)` statements in services |
| `join fetch` | `joinedload(...)` |
| DTO records + `@Valid` | Pydantic models (`schemas.py`) |
| `JwtAuthFilter` + `SecurityConfig` | `Depends(get_current_user)` / `Depends(require_admin)` |
| `@RestControllerAdvice` | `@app.exception_handler` in `errors.py` |
| `@Transactional` | one SQLAlchemy session per request, `db.commit()` |
| `CommandLineRunner` (DataSeeder) | `lifespan` startup in `main.py` → `seed()` |
| `application.properties` | `config.py` + `.env` |
| MySQL | SQLite |
| Separate FastAPI ML service over REST | ML code called directly in the same app |

## API overview

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register`, `/api/auth/login` | Returns `{token, user}` |
| GET, PUT | `/api/users/me` | Current user profile |
| GET | `/api/users/search?skill=` | Users who teach a skill |
| GET | `/api/matches` | Smart matches |
| GET | `/api/dashboard` | Dashboard counts and lists |
| GET, POST, PUT, DELETE | `/api/skills/me`, `/api/skills`, `/api/skills/{id}` | Skill management |
| POST, GET, PUT | `/api/swap-requests`, `/incoming`, `/outgoing`, `/accepted`, `/{id}/accept`, `/reject`, `/cancel` | Swap requests |
| POST, GET, PUT | `/api/sessions`, `/me`, `/{id}/complete`, `/{id}/cancel` | Sessions |
| POST, GET | `/api/ratings`, `/api/users/{id}/ratings` | Ratings |
| GET | `/api/recommendations` | AI Picks |
| GET, POST | `/api/skill-tests/skills/{id}/status`, `/start`, `/api/skill-tests/{id}/submit`, `/result` | Skill test |
| GET, PUT, DELETE | `/api/admin/stats`, `/users`, `/users/{id}/status`, `/users/{id}`, `/sessions` | Admin only |

## Troubleshooting

| Problem | Fix |
|---|---|
| Skill test says GROQ_API_KEY isn't set | Add it to `.env` (Docker) or `backend/.env` (local) and restart the backend |
| Groq model error in the logs | Groq retires models over time. Set `GROQ_MODEL` to a current one from https://console.groq.com/docs/models |
| Port 8000 or 3000 already in use | Stop the other program, or change the port in `docker-compose.yml` / the uvicorn command |
| Want a clean database | Stop the backend and delete `backend/data/skillswap.db` (Docker: `docker compose down -v`) |
| Logged out unexpectedly | Tokens expire after 24 hours. Sign in again |

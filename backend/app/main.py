"""
SkillSwap backend (FastAPI). Entry point: uvicorn app.main:app

Startup order (lifespan):
  1. create any missing tables in the database
  2. seed the admin account and demo users
  3. load the recommendation model into memory
Then every request:  CORS -> route -> dependencies (DB session, current user) -> service -> JSON.
Interactive API docs: http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  (registers every table on Base.metadata)
from .config import settings
from .database import Base, SessionLocal, engine
from .errors import register_error_handlers
from .ml.recommender import get_recommender
from .routers import api, skill_tests
from .seed import seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("skillswap")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)       # like ddl-auto=update for new tables
    with SessionLocal() as db:
        seed(db)
    try:
        model = get_recommender()
        log.info("Recommendation model ready (%d skills)", len(model.vocab))
    except Exception as exc:                     # the app still works; AI Picks falls back to popular skills
        log.warning("Recommendation model not loaded: %s", exc)
    yield


app = FastAPI(title="SkillSwap API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

register_error_handlers(app)

for router in api.ROUTERS:
    app.include_router(router)
app.include_router(skill_tests.router)

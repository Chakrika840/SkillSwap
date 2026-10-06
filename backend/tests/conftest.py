import os
import tempfile
from pathlib import Path

import pytest

# Use a throwaway database and no real AI key BEFORE the app is imported.
_tmp = Path(tempfile.mkdtemp(prefix="skillswap-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["GROQ_API_KEY"] = ""
os.environ["SEED_DEMO_USERS"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    """A fresh database (admin + 5 demo users) for every test."""
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:          # 'with' runs the startup: create tables + seed
        yield c


def login(client, email, password="demo1234"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def aarav(client):
    return login(client, "aarav@demo.com")


@pytest.fixture()
def diya(client):
    return login(client, "diya@demo.com")


@pytest.fixture()
def admin(client):
    return login(client, "admin@skillswap.com", "admin123")

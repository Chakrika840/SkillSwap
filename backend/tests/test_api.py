"""End-to-end API tests: every feature, through real HTTP calls, on a fresh database."""
from datetime import datetime, timedelta

from conftest import login


def skill_id(client, headers, name):
    return next(s["id"] for s in client.get("/api/skills/me", headers=headers).json() if s["name"] == name)


# ------------------------------------------------------------------ auth and errors
def test_health_and_auth_errors(client):
    assert client.get("/api/health").json()["status"] == "ok"

    r = client.get("/api/users/me")
    assert r.status_code == 401
    assert r.json() == {"status": 401, "message": "Please sign in to continue."}

    r = client.get("/api/users/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401

    r = client.post("/api/auth/login", json={"email": "aarav@demo.com", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["message"] == "Email or password is incorrect."


def test_register_validation_and_duplicates(client):
    r = client.post("/api/auth/register", json={"name": "Ravi", "email": "Ravi@Mail.com ", "password": "secret1"})
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "ravi@mail.com"
    assert body["user"]["ratingCount"] == 0 and "password" not in body["user"]   # camelCase, no hash

    r = client.post("/api/auth/register", json={"name": "Ravi", "email": "ravi@mail.com", "password": "secret1"})
    assert r.status_code == 409

    r = client.post("/api/auth/register", json={"name": "", "email": "bad", "password": "123"})
    assert r.status_code == 400
    msg = r.json()["message"]
    assert "name:" in msg and "email:" in msg and "password:" in msg

    r = client.post("/api/auth/register", content="{broken json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_profile_update(client, aarav):
    r = client.put("/api/users/me", headers=aarav, json={"name": "  Aarav R ", "city": " ", "bio": "Hi"})
    assert r.status_code == 200
    assert r.json()["name"] == "Aarav R" and r.json()["city"] is None


# ------------------------------------------------------------------ skills
def test_skill_crud_and_ownership(client, aarav, diya):
    r = client.post("/api/skills", headers=aarav, json={"name": "  Docker   Compose ", "level": "BEGINNER",
                                                         "type": "OFFERED"})
    assert r.status_code == 201 and r.json()["name"] == "Docker Compose"
    new_id = r.json()["id"]

    r = client.post("/api/skills", headers=aarav, json={"name": "docker compose", "level": "ADVANCED",
                                                         "type": "OFFERED"})
    assert r.status_code == 409

    r = client.post("/api/skills", headers=aarav, json={"name": "Go", "level": "EXPERT", "type": "OFFERED"})
    assert r.status_code == 400

    assert client.put(f"/api/skills/{new_id}", headers=diya,
                      json={"name": "x", "level": "BEGINNER", "type": "OFFERED"}).status_code == 403
    r = client.put(f"/api/skills/{new_id}", headers=aarav,
                   json={"name": "Docker Compose", "level": "INTERMEDIATE", "type": "OFFERED"})
    assert r.json()["level"] == "INTERMEDIATE"
    assert client.delete(f"/api/skills/{new_id}", headers=aarav).status_code == 204
    assert client.delete(f"/api/skills/{new_id}", headers=aarav).status_code == 404
    assert client.get("/api/skills/abc", headers=aarav).status_code in (400, 405)


# ------------------------------------------------------------------ matching and search
def test_smart_matching_scores(client, aarav):
    cards = client.get("/api/matches", headers=aarav).json()
    scores = {c["name"]: c["matchScore"] for c in cards}
    # Diya: teaches Python (Intermediate +6), wants Java, same city -> 35 + 6 + 35 + 5
    assert scores["Diya Sharma"] == 81
    # Kiran: teaches UI Design (Advanced +10), wants Java, other city -> 35 + 10 + 35
    assert scores["Kiran Rao"] == 80
    # Rohan only wants Spring Boot, which Aarav teaches -> 35
    assert scores["Rohan Das"] == 35
    assert "Meera Iyer" not in scores
    assert cards[0]["name"] == "Diya Sharma"
    assert cards[0]["matchReasons"][0] == "You can teach each other"


def test_search(client, aarav):
    names = [c["name"] for c in client.get("/api/users/search", params={"skill": "pyth"}, headers=aarav).json()]
    assert names == ["Diya Sharma"]
    everyone = client.get("/api/users/search", headers=aarav).json()
    assert len(everyone) == 4 and all(c["name"] != "Aarav Reddy" for c in everyone)


# ------------------------------------------------------------------ swap -> session -> rating
def test_full_swap_session_rating_flow(client, aarav, diya):
    diya_id = client.get("/api/users/me", headers=diya).json()["id"]

    assert client.post("/api/swap-requests", headers=aarav,
                       json={"toUserId": diya_id, "skillName": "Rust"}).status_code == 400
    assert client.post("/api/swap-requests", headers=aarav,
                       json={"toUserId": diya_id, "skillName": "python", "offeredSkillName": "Go"}).status_code == 400

    r = client.post("/api/swap-requests", headers=aarav,
                    json={"toUserId": diya_id, "skillName": "python", "offeredSkillName": "java", "message": "Hi!"})
    assert r.status_code == 201
    swap = r.json()
    assert swap["skillName"] == "Python" and swap["offeredSkillName"] == "Java" and swap["status"] == "PENDING"
    assert client.post("/api/swap-requests", headers=aarav,
                       json={"toUserId": diya_id, "skillName": "Python"}).status_code == 409

    assert client.put(f"/api/swap-requests/{swap['id']}/accept", headers=aarav).status_code == 403
    assert len(client.get("/api/swap-requests/incoming", headers=diya).json()) == 1
    assert client.put(f"/api/swap-requests/{swap['id']}/accept", headers=diya).json()["status"] == "ACCEPTED"
    assert client.put(f"/api/swap-requests/{swap['id']}/accept", headers=diya).status_code == 409
    assert len(client.get("/api/swap-requests/accepted", headers=aarav).json()) == 1

    past = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    assert client.post("/api/sessions", headers=aarav, json={
        "swapRequestId": swap["id"], "scheduledAt": past, "durationMinutes": 60}).status_code == 400

    future = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    r = client.post("/api/sessions", headers=aarav, json={
        "swapRequestId": swap["id"], "scheduledAt": future, "durationMinutes": 60, "iAmTeacher": False})
    assert r.status_code == 201
    session = r.json()
    assert session["skillTopic"] == "Python" and session["myRole"] == "LEARNER"
    assert session["teacher"]["name"] == "Diya Sharma"
    assert session["meetingLink"].startswith("https://meet.jit.si/SkillSwap-")

    dash = client.get("/api/dashboard", headers=aarav).json()
    assert dash["activeSwaps"] == 1 and dash["upcomingSessions"] == 1 and len(dash["topMatches"]) == 3

    assert client.post("/api/ratings", headers=aarav,
                       json={"sessionId": session["id"], "score": 5}).status_code == 400   # not completed yet
    assert client.put(f"/api/sessions/{session['id']}/complete", headers=diya).json()["status"] == "COMPLETED"

    r = client.post("/api/ratings", headers=aarav, json={"sessionId": session["id"], "score": 5, "comment": "Great"})
    assert r.status_code == 201
    assert client.post("/api/ratings", headers=aarav,
                       json={"sessionId": session["id"], "score": 4}).status_code == 409
    assert client.post("/api/ratings", headers=diya,
                       json={"sessionId": session["id"], "score": 9}).status_code == 400

    received = client.get(f"/api/users/{diya_id}/ratings", headers=aarav).json()
    assert received[0]["fromName"] == "Aarav Reddy" and received[0]["score"] == 5
    assert client.get("/api/users/me", headers=diya).json()["rating"] == 5.0
    sessions = client.get("/api/sessions/me", headers=aarav).json()
    assert sessions[0]["ratedByMe"] is True


# ------------------------------------------------------------------ AI Picks
def test_recommendations(client, aarav):
    picks = client.get("/api/recommendations", headers=aarav).json()
    assert 0 < len(picks) <= 8
    assert picks[0]["score"] == 100 and picks[0]["source"] == "ML model"
    mine = {"java", "spring boot", "python", "ui design"}
    assert not any(p["skill"].lower() in mine for p in picks)


def test_recommendations_fallback_for_new_user(client):
    client.post("/api/auth/register", json={"name": "New", "email": "new@x.com", "password": "secret1"})
    headers = login(client, "new@x.com", "secret1")
    picks = client.get("/api/recommendations", headers=headers).json()
    assert picks and picks[0]["source"] == "Popular on SkillSwap"


# ------------------------------------------------------------------ admin
def test_admin_permissions_suspend_and_delete(client, admin, aarav):
    assert client.get("/api/admin/stats", headers=aarav).status_code == 403
    stats = client.get("/api/admin/stats", headers=admin).json()
    assert stats["users"] == 5 and stats["skills"] == 20

    users = client.get("/api/admin/users", headers=admin).json()
    aarav_id = next(u["id"] for u in users if u["email"] == "aarav@demo.com")
    admin_id = next(u["id"] for u in users if u["role"] == "ADMIN")
    assert client.put(f"/api/admin/users/{admin_id}/status", headers=admin,
                      json={"active": False}).status_code == 400

    assert client.put(f"/api/admin/users/{aarav_id}/status", headers=admin,
                      json={"active": False}).json()["active"] is False
    assert client.get("/api/users/me", headers=aarav).status_code == 401          # old token stops working
    r = client.post("/api/auth/login", json={"email": "aarav@demo.com", "password": "demo1234"})
    assert r.status_code == 403
    diya = login(client, "diya@demo.com")
    assert all(c["name"] != "Aarav Reddy" for c in client.get("/api/matches", headers=diya).json())

    assert client.delete(f"/api/admin/users/{aarav_id}", headers=admin).status_code == 204
    assert client.get("/api/admin/stats", headers=admin).json()["users"] == 4


# ------------------------------------------------------------------ AI skill test
def _fake_questions(skill, level, count, avoid):
    from app.ml.question_generator import GeneratedQuestion
    return [GeneratedQuestion(question=f"{skill} {level} question {i}?",
                              options=[f"right {i}", f"wrong a{i}", f"wrong b{i}", f"wrong c{i}"],
                              correctIndex=0, explanation="Because.") for i in range(count)]


def test_skill_test_pass_and_rules(client, aarav, diya, monkeypatch):
    from app.services import skill_test
    monkeypatch.setattr(skill_test, "generate_questions", _fake_questions)

    java = skill_id(client, aarav, "Java")              # ADVANCED, OFFERED
    wanted = skill_id(client, aarav, "Python")          # WANTED
    assert client.post(f"/api/skill-tests/skills/{wanted}/start", headers=aarav).status_code == 400
    assert client.post(f"/api/skill-tests/skills/{java}/start", headers=diya).status_code == 403

    status = client.get(f"/api/skill-tests/skills/{java}/status", headers=aarav).json()
    assert status["canStart"] is True and status["questionsPerTest"] == 10

    test = client.post(f"/api/skill-tests/skills/{java}/start", headers=aarav).json()
    assert len(test["questions"]) == 10 and test["secondsRemaining"] > 590
    assert "correctIndex" not in str(test)              # answers never reach the browser
    again = client.post(f"/api/skill-tests/skills/{java}/start", headers=aarav).json()
    assert again["testId"] == test["testId"]            # refresh resumes the same attempt

    # Answer every question correctly: the right option text starts with "right".
    answers = [{"questionId": q["questionId"],
                "selectedKey": next(o["key"] for o in q["options"] if o["text"].startswith("right"))}
               for q in test["questions"]]
    result = client.post(f"/api/skill-tests/{test['testId']}/submit", headers=aarav,
                         json={"answers": answers}).json()
    assert result["status"] == "PASSED" and result["score"] == 100 and result["verifiedLevel"] == "ADVANCED"
    assert result["review"][0]["correctIndex"] == 0
    assert client.post(f"/api/skill-tests/{test['testId']}/submit", headers=aarav, json={}).status_code == 409

    skill = next(s for s in client.get("/api/skills/me", headers=aarav).json() if s["id"] == java)
    assert skill["verified"] is True and skill["verificationScore"] == 100
    assert client.post(f"/api/skill-tests/skills/{java}/start", headers=aarav).status_code == 409

    # Diya now sees the verified bonus (+10) on Aarav's card.
    card = next(c for c in client.get("/api/matches", headers=diya).json() if c["name"] == "Aarav Reddy")
    assert card["matchScore"] == 35 + 10 + 10 + 35 + 5


def test_skill_test_partial_and_cooldown(client, aarav, monkeypatch):
    from app.services import skill_test
    monkeypatch.setattr(skill_test, "generate_questions", _fake_questions)
    java = skill_id(client, aarav, "Java")
    test = client.post(f"/api/skill-tests/skills/{java}/start", headers=aarav).json()

    # 6 of 10 correct = 60% -> verified one level lower (INTERMEDIATE)
    answers = []
    for i, q in enumerate(test["questions"]):
        want_right = i < 6
        key = next(o["key"] for o in q["options"] if o["text"].startswith("right") == want_right)
        answers.append({"questionId": q["questionId"], "selectedKey": key})
    result = client.post(f"/api/skill-tests/{test['testId']}/submit", headers=aarav,
                         json={"answers": answers}).json()
    assert result["score"] == 60 and result["verifiedLevel"] == "INTERMEDIATE"
    assert result["retryAvailableAt"].endswith("Z")

    r = client.post(f"/api/skill-tests/skills/{java}/start", headers=aarav)
    assert r.status_code == 429
    status = client.get(f"/api/skill-tests/skills/{java}/status", headers=aarav).json()
    assert status["canStart"] is False and status["retryAvailableAt"]


def test_skill_test_without_ai_key_gives_clear_error(client, aarav):
    java = skill_id(client, aarav, "Java")
    r = client.post(f"/api/skill-tests/skills/{java}/start", headers=aarav)
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["message"]


def test_decide_level_rules():
    from app.models import ProficiencyLevel as L
    from app.services.skill_test import decide_level
    assert decide_level(L.ADVANCED, 80) == L.ADVANCED
    assert decide_level(L.ADVANCED, 79) == L.INTERMEDIATE
    assert decide_level(L.INTERMEDIATE, 50) == L.BEGINNER
    assert decide_level(L.BEGINNER, 70) is None
    assert decide_level(L.ADVANCED, 49) is None

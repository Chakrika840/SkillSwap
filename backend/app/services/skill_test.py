"""
AI skill verification test.

Rules:  10 questions, 10 minutes.  >= 80% -> verified at the claimed level.
        50-79% -> verified one level lower (not possible for Beginner).  < 50% -> not verified.
        24-hour wait before retrying after anything but a full pass.

Anti-cheating: correct answers never leave the server, options are shuffled per attempt,
the timer is enforced on the server, a test can be submitted only once.
"""
import json
import logging
import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, joinedload

from ..errors import ApiError
from ..ml.question_generator import GeneratedQuestion, QuestionGenerationError, generate_questions
from ..models import ProficiencyLevel, Skill, SkillTest, SkillType, TestAnswer, TestQuestion, TestStatus, User
from ..schemas import (OptionView, QuestionView, ReviewItem, SkillTestStatusResponse, StartTestResponse,
                       SubmitTestRequest, TestResultResponse)
from ..timeutil import iso_utc, now_utc

log = logging.getLogger("skillswap.skilltest")

QUESTIONS_PER_TEST = 10
DURATION_SECONDS = 600              # 10 minutes
PASS_SCORE = 80                     # verified at the claimed level
PARTIAL_SCORE = 50                  # verified one level lower
GRACE_SECONDS = 30                  # allowance for network delay
COOLDOWN = timedelta(hours=24)
BANK_TARGET = 30                    # stop calling the LLM once a skill + level has this many questions
AVOID_LIMIT = 25

_random = random.SystemRandom()     # cryptographically strong shuffling


# ------------------------------------------------------------------ status
def get_status(db: DbSession, me: User, skill_id: int) -> SkillTestStatusResponse:
    skill = _owned_skill(db, me, skill_id)
    now = now_utc()
    active = _active_test(db, me.id, skill.id, now)
    db.commit()                                         # persists an expiry, if one happened
    retry_at = _retry_available_at(db, me.id, skill, now)
    fully_verified = _is_fully_verified(skill)
    return SkillTestStatusResponse(
        skill_id=skill.id, skill_name=skill.name, level=skill.level.value, verified=skill.verified,
        verified_level=_name(skill.verified_level), verification_score=skill.verification_score,
        test_in_progress=active is not None,
        seconds_remaining=_seconds_remaining(active, now) if active else 0,
        retry_available_at=iso_utc(retry_at),
        can_start=not fully_verified and (active is not None or retry_at is None),
        questions_per_test=QUESTIONS_PER_TEST, duration_seconds=DURATION_SECONDS,
        pass_score=PASS_SCORE, partial_score=PARTIAL_SCORE,
    )


# ------------------------------------------------------------------ start
def start_test(db: DbSession, me: User, skill_id: int) -> StartTestResponse:
    """Starts a new test, or resumes the one already running (a page refresh keeps the same timer)."""
    skill = _owned_skill(db, me, skill_id)
    now = now_utc()

    active = _active_test(db, me.id, skill.id, now)
    if active is not None:
        return _start_response(db, active, now)
    db.commit()
    if _is_fully_verified(skill):
        raise ApiError.conflict(f"This skill is already verified at {_label(skill.level)}.")
    if _retry_available_at(db, me.id, skill, now) is not None:
        raise ApiError.too_many("You can retake this test 24 hours after your last attempt.")

    skill_key = normalize_skill(skill.name)
    if not skill_key:
        raise ApiError.bad_request("This skill has no name.")

    # End the read transaction BEFORE the slow AI call (~20 s), so no database connection is held meanwhile.
    db.commit()
    bank = _ensure_question_bank(db, skill_key, skill.name.strip(), skill.level)
    picked = _random.sample(bank, QUESTIONS_PER_TEST)

    test = SkillTest(user_id=me.id, skill_id=skill.id, skill_name=skill.name.strip(), claimed_level=skill.level,
                     status=TestStatus.IN_PROGRESS, total_questions=len(picked), started_at=now,
                     expires_at=now + timedelta(seconds=DURATION_SECONDS))
    for position, question in enumerate(picked, start=1):
        test.answers.append(TestAnswer(question=question, position=position, option_order=_shuffled_order()))
    db.add(test)
    db.commit()                                          # test + its 10 rows saved together
    return _start_response(db, test, now)


# ------------------------------------------------------------------ submit
def submit_test(db: DbSession, me: User, test_id: int, request: SubmitTestRequest | None) -> TestResultResponse:
    test = _owned_test(db, me, test_id)
    if test.status != TestStatus.IN_PROGRESS:
        raise ApiError.conflict("This test has already been submitted.")

    now = now_utc()
    rows = _rows(db, test.id)
    if now > test.expires_at + timedelta(seconds=GRACE_SECONDS):   # the server's clock decides, not the browser's
        _expire(test)
        db.commit()
        return _result(test, rows)

    chosen: dict[int, int] = {}
    for answer in (request.answers if request else []):
        if answer and answer.question_id is not None and answer.selected_key is not None \
                and 0 <= answer.selected_key <= 3:
            chosen[answer.question_id] = answer.selected_key

    correct = 0
    for row in rows:
        selected = chosen.get(row.question_id)
        row.selected_index = selected
        # selected_key is the ORIGINAL option index, so the shuffle doesn't affect grading.
        row.correct = selected is not None and selected == row.question.correct_index
        correct += row.correct

    total = len(rows)
    score = int(correct * 100 / total + 0.5) if total else 0
    verified = decide_level(test.claimed_level, score)

    test.correct_count = correct
    test.score = score
    test.submitted_at = now
    test.verified_level = verified
    test.status = TestStatus.PASSED if verified else TestStatus.FAILED
    if verified:
        _apply_verification(db, test.skill_id, verified, score)
    db.commit()
    return _result(test, rows)


def get_result(db: DbSession, me: User, test_id: int) -> TestResultResponse:
    test = _owned_test(db, me, test_id)
    rows = _rows(db, test.id)
    if test.status == TestStatus.IN_PROGRESS:
        if now_utc() > test.expires_at + timedelta(seconds=GRACE_SECONDS):
            _expire(test)
            db.commit()
        else:
            raise ApiError.conflict("This test is still in progress.")
    return _result(test, rows)


# ------------------------------------------------------------------ scoring rules
def decide_level(claimed: ProficiencyLevel, score: int) -> ProficiencyLevel | None:
    """>= 80%: claimed level. 50-79%: one level lower (not possible for Beginner). Else: None."""
    if score >= PASS_SCORE:
        return claimed
    if score >= PARTIAL_SCORE and claimed.rank > 0:
        return list(ProficiencyLevel)[claimed.rank - 1]
    return None


def _apply_verification(db: DbSession, skill_id: int, verified: ProficiencyLevel, score: int) -> None:
    """Updates the skill's badge, but never lowers an existing verification."""
    skill = db.get(Skill, skill_id)
    if skill is None:
        return
    current = skill.verified_level if skill.verified else None
    if current is None or verified.rank >= current.rank:
        skill.verified, skill.verified_level, skill.verification_score = True, verified, score


def _is_fully_verified(skill: Skill) -> bool:
    return skill.verified and skill.verified_level == skill.level


def _retry_available_at(db: DbSession, user_id: int, skill: Skill, now: datetime) -> datetime | None:
    """When the next attempt is allowed, or None if it is allowed now."""
    if _is_fully_verified(skill):
        return None
    last = db.scalar(select(SkillTest).where(
        SkillTest.user_id == user_id, SkillTest.skill_id == skill.id, SkillTest.status != TestStatus.IN_PROGRESS,
        SkillTest.submitted_at.is_not(None)).order_by(SkillTest.submitted_at.desc()).limit(1))
    if last is None:
        return None
    retry_at = last.submitted_at + COOLDOWN
    return retry_at if now < retry_at else None


def _active_test(db: DbSession, user_id: int, skill_id: int, now: datetime) -> SkillTest | None:
    """The running test, if its time is not up; a test whose time ran out is marked EXPIRED."""
    test = db.scalar(select(SkillTest).where(
        SkillTest.user_id == user_id, SkillTest.skill_id == skill_id, SkillTest.status == TestStatus.IN_PROGRESS,
    ).order_by(SkillTest.started_at.desc()).limit(1))
    if test is not None and now > test.expires_at + timedelta(seconds=GRACE_SECONDS):
        _expire(test)
        return None
    return test


def _expire(test: SkillTest) -> None:
    test.status = TestStatus.EXPIRED
    test.score = 0
    test.correct_count = 0
    test.submitted_at = test.expires_at


# ------------------------------------------------------------------ question bank
def normalize_skill(name: str | None) -> str:
    return " ".join((name or "").lower().split())[:60]


def _ensure_question_bank(db: DbSession, skill_key: str, display_name: str,
                          level: ProficiencyLevel) -> list[TestQuestion]:
    """Reuse stored questions; ask the LLM only while the bank is smaller than BANK_TARGET."""
    bank = list(db.scalars(select(TestQuestion).where(TestQuestion.skill_key == skill_key,
                                                      TestQuestion.level == level)).all())
    if len(bank) >= BANK_TARGET:
        return bank

    try:
        existing = [q.question for q in bank]
        _random.shuffle(existing)
        generated = generate_questions(display_name, level.value, QUESTIONS_PER_TEST, existing[:AVOID_LIMIT])

        seen = {_normalize_text(q.question) for q in bank}
        fresh = []
        for g in generated:
            key = _normalize_text(g.question)
            if _is_valid(g) and key not in seen:
                seen.add(key)
                fresh.append(TestQuestion(skill_key=skill_key, level=level, question=g.question.strip(),
                                          options_json=json.dumps([o.strip() for o in g.options]),
                                          correct_index=g.correctIndex, explanation=(g.explanation or "").strip()))
        if fresh:
            db.add_all(fresh)
            db.commit()
            bank.extend(fresh)
    except QuestionGenerationError as exc:
        if len(bank) >= QUESTIONS_PER_TEST:
            log.warning("Question generation failed for '%s' (%s); using the existing bank of %d",
                        skill_key, exc.message, len(bank))
            return bank
        raise _friendly_error(exc, display_name) from exc

    if len(bank) < QUESTIONS_PER_TEST:
        raise ApiError.unavailable("Not enough questions could be prepared for this skill yet. Try again in a minute.")
    return bank


def _friendly_error(exc: QuestionGenerationError, skill: str) -> ApiError:
    if exc.status_code == 422:
        return ApiError(422, f'"{skill}" can\'t be tested automatically. Check the skill name, or use its most '
                             f'common name (for example "JavaScript" instead of "JS stuff").')
    if exc.status_code == 429:
        return ApiError.too_many("The test generator is busy. Try again in a minute.")
    if "GROQ_API_KEY" in exc.message:
        return ApiError.unavailable(exc.message)
    return ApiError.unavailable("The test generator is unavailable right now. Try again shortly.")


def _is_valid(g: GeneratedQuestion) -> bool:
    return (bool(g.question and g.question.strip()) and len(g.options) == 4
            and all(o and o.strip() for o in g.options) and 0 <= g.correctIndex <= 3)


def _normalize_text(text: str | None) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isascii() and ch.isalnum())


# ------------------------------------------------------------------ mapping to responses
def _rows(db: DbSession, test_id: int) -> list[TestAnswer]:
    return list(db.scalars(select(TestAnswer).options(joinedload(TestAnswer.question))
                           .where(TestAnswer.test_id == test_id).order_by(TestAnswer.position)).all())


def _start_response(db: DbSession, test: SkillTest, now: datetime) -> StartTestResponse:
    questions = []
    for row in _rows(db, test.id):
        options = json.loads(row.question.options_json)
        shown = [OptionView(key=k, text=options[k]) for k in (int(x) for x in row.option_order.split(","))]
        questions.append(QuestionView(question_id=row.question_id, position=row.position,
                                      question=row.question.question, options=shown))
    return StartTestResponse(
        test_id=test.id, skill_id=test.skill_id, skill_name=test.skill_name, level=test.claimed_level.value,
        total_questions=test.total_questions, duration_seconds=DURATION_SECONDS,
        seconds_remaining=_seconds_remaining(test, now), expires_at=iso_utc(test.expires_at), questions=questions,
    )


def _result(test: SkillTest, rows: list[TestAnswer]) -> TestResultResponse:
    review = [ReviewItem(position=r.position, question=r.question.question,
                         options=json.loads(r.question.options_json), selected_index=r.selected_index,
                         correct_index=r.question.correct_index, correct=bool(r.correct),
                         explanation=r.question.explanation) for r in rows]
    full_pass = test.status == TestStatus.PASSED and test.verified_level == test.claimed_level
    retry_at = test.submitted_at + COOLDOWN if (not full_pass and test.submitted_at) else None
    return TestResultResponse(
        test_id=test.id, skill_id=test.skill_id, skill_name=test.skill_name,
        claimed_level=test.claimed_level.value, status=test.status.value, score=test.score or 0,
        correct_count=test.correct_count or 0, total_questions=test.total_questions,
        verified_level=_name(test.verified_level), retry_available_at=iso_utc(retry_at), review=review,
    )


# ------------------------------------------------------------------ helpers
def _owned_skill(db: DbSession, me: User, skill_id: int) -> Skill:
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise ApiError.not_found("Skill not found.")
    if skill.user_id != me.id:
        raise ApiError.forbidden("You can only verify your own skills.")
    if skill.type != SkillType.OFFERED:
        raise ApiError.bad_request("Only skills you teach can be verified.")
    return skill


def _owned_test(db: DbSession, me: User, test_id: int) -> SkillTest:
    test = db.get(SkillTest, test_id)
    if test is None:
        raise ApiError.not_found("Test not found.")
    if test.user_id != me.id:
        raise ApiError.forbidden("This test belongs to another user.")
    return test


def _seconds_remaining(test: SkillTest, now: datetime) -> int:
    return max(0, int((test.expires_at - now).total_seconds()))


def _shuffled_order() -> str:
    order = [0, 1, 2, 3]
    _random.shuffle(order)
    return ",".join(map(str, order))


def _name(level: ProficiencyLevel | None) -> str | None:
    return level.value if level else None


def _label(level: ProficiencyLevel) -> str:
    return level.value.capitalize()

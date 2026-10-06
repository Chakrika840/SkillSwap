"""
Business logic for accounts, skills, swap requests, sessions, ratings, dashboard and admin.
Routers stay thin: they read the request, call one function here, and return its result.
Each function that changes data ends with db.commit() (one transaction per action).
"""
import secrets
from datetime import timedelta

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session as DbSession, joinedload

from ..errors import ApiError
from ..models import (Rating, Role, Session, SessionStatus, Skill, SkillTest, SkillType, SwapRequest,
                      SwapStatus, TestAnswer, User)
from ..schemas import (AdminStatsDto, AuthResponse, DashboardDto, LoginRequest, RatingCreate, RatingDto,
                       RegisterRequest, SessionCreate, SessionDto, SkillDto, SkillRequest, SwapRequestCreate,
                       SwapRequestDto, UpdateProfileRequest, UserDto)
from ..security import create_token, hash_password, verify_password
from ..timeutil import now_local
from . import matching


def _clean(value: str | None) -> str | None:
    """Blank -> None, otherwise trimmed."""
    return value.strip() if value and value.strip() else None


def _normalize_email(email: str) -> str:
    return email.strip().lower()


# ============================================================ auth
def register(db: DbSession, req: RegisterRequest) -> AuthResponse:
    email = _normalize_email(req.email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise ApiError.conflict("An account with this email already exists. Sign in instead.")
    user = User(name=req.name.strip(), email=email, password=hash_password(req.password), role=Role.USER)
    db.add(user)
    db.commit()
    return AuthResponse(token=create_token(user.email, user.role.value), user=UserDto.of(user))


def login(db: DbSession, req: LoginRequest) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == _normalize_email(req.email)))
    # Same message for "no such email" and "wrong password", so attackers can't probe emails.
    if user is None or not verify_password(req.password, user.password):
        raise ApiError.unauthorized("Email or password is incorrect.")
    if not user.active:
        raise ApiError.forbidden("This account has been suspended. Contact the administrator.")
    return AuthResponse(token=create_token(user.email, user.role.value), user=UserDto.of(user))


def update_profile(db: DbSession, me: User, req: UpdateProfileRequest) -> UserDto:
    me.name = req.name.strip()
    me.city = _clean(req.city)
    me.bio = _clean(req.bio)
    db.commit()
    return UserDto.of(me)


# ============================================================ skills
def clean_skill_name(raw: str | None) -> str:
    """'  react   js ' -> 'react js' (keeps the user's capital letters)."""
    name = " ".join((raw or "").split())
    if not name:
        raise ApiError.bad_request("Skill name is required.")
    return name


def my_skills(db: DbSession, me: User) -> list[SkillDto]:
    rows = db.scalars(select(Skill).where(Skill.user_id == me.id)
                      .order_by(Skill.created_at.desc(), Skill.id.desc())).all()
    return [SkillDto.of(s) for s in rows]


def add_skill(db: DbSession, me: User, req: SkillRequest) -> SkillDto:
    name = clean_skill_name(req.name)
    duplicate = db.scalar(select(Skill.id).where(
        Skill.user_id == me.id, Skill.type == req.type, func.lower(Skill.name) == name.lower()))
    if duplicate:
        raise ApiError.conflict(f"You already listed {name}.")
    skill = Skill(name=name, level=req.level, type=req.type, user_id=me.id)
    db.add(skill)
    db.commit()
    return SkillDto.of(skill)


def update_skill(db: DbSession, me: User, skill_id: int, req: SkillRequest) -> SkillDto:
    skill = _owned_skill(db, me, skill_id)
    name = clean_skill_name(req.name)
    changed = skill.name.lower() != name.lower() or skill.level != req.level or skill.type != req.type
    skill.name, skill.level, skill.type = name, req.level, req.type
    if changed:
        # A different skill or level must be verified again (stops "pass Beginner, edit to Advanced").
        skill.verified, skill.verified_level, skill.verification_score = False, None, None
    db.commit()
    return SkillDto.of(skill)


def delete_skill(db: DbSession, me: User, skill_id: int) -> None:
    db.delete(_owned_skill(db, me, skill_id))
    db.commit()


def _owned_skill(db: DbSession, me: User, skill_id: int) -> Skill:
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise ApiError.not_found("Skill not found.")
    if skill.user_id != me.id:
        raise ApiError.forbidden("You can only change your own skills.")
    return skill


# ============================================================ swap requests
def _swap_query():
    # Load both users in the same query (no extra query per row).
    return select(SwapRequest).options(joinedload(SwapRequest.from_user), joinedload(SwapRequest.to_user))


def create_swap(db: DbSession, me: User, req: SwapRequestCreate) -> SwapRequestDto:
    if req.to_user_id == me.id:
        raise ApiError.bad_request("You can't send a swap request to yourself.")
    receiver = db.get(User, req.to_user_id)
    if receiver is None or not receiver.active:
        raise ApiError.not_found("That user is not available.")

    wanted = db.scalar(select(Skill).where(
        Skill.user_id == receiver.id, Skill.type == SkillType.OFFERED,
        func.lower(Skill.name) == req.skill_name.strip().lower()))
    if wanted is None:
        raise ApiError.bad_request(f"{receiver.name} doesn't teach {req.skill_name}.")

    offered = None
    if _clean(req.offered_skill_name):
        offered = db.scalar(select(Skill.name).where(
            Skill.user_id == me.id, Skill.type == SkillType.OFFERED,
            func.lower(Skill.name) == req.offered_skill_name.strip().lower()))
        if offered is None:
            raise ApiError.bad_request(f"Add {req.offered_skill_name} to the skills you teach before offering it.")

    duplicate = db.scalar(select(func.count(SwapRequest.id)).where(
        SwapRequest.from_user_id == me.id, SwapRequest.to_user_id == receiver.id,
        func.lower(SwapRequest.skill_name) == wanted.name.lower(), SwapRequest.status == SwapStatus.PENDING))
    if duplicate:
        raise ApiError.conflict(f"You already have a pending request to {receiver.name} for {wanted.name}.")

    swap = SwapRequest(from_user_id=me.id, to_user_id=receiver.id, skill_name=wanted.name,
                       skill_level=wanted.level, offered_skill_name=offered, message=_clean(req.message))
    db.add(swap)
    db.commit()
    return SwapRequestDto.of(db.scalar(_swap_query().where(SwapRequest.id == swap.id)))


def incoming_swaps(db: DbSession, me: User) -> list[SwapRequestDto]:
    rows = db.scalars(_swap_query().where(SwapRequest.to_user_id == me.id)
                      .order_by(SwapRequest.created_at.desc(), SwapRequest.id.desc())).all()
    return [SwapRequestDto.of(r) for r in rows]


def outgoing_swaps(db: DbSession, me: User) -> list[SwapRequestDto]:
    rows = db.scalars(_swap_query().where(SwapRequest.from_user_id == me.id)
                      .order_by(SwapRequest.created_at.desc(), SwapRequest.id.desc())).all()
    return [SwapRequestDto.of(r) for r in rows]


def accepted_swaps(db: DbSession, me: User) -> list[SwapRequestDto]:
    rows = db.scalars(_swap_query().where(
        SwapRequest.status == SwapStatus.ACCEPTED,
        or_(SwapRequest.from_user_id == me.id, SwapRequest.to_user_id == me.id),
    ).order_by(SwapRequest.responded_at.desc())).all()
    return [SwapRequestDto.of(r) for r in rows]


def respond_swap(db: DbSession, me: User, swap_id: int, accept: bool) -> SwapRequestDto:
    swap = _find_swap(db, swap_id)
    if swap.to_user_id != me.id:
        raise ApiError.forbidden("Only the person who received this request can respond to it.")
    _require_pending(swap)
    swap.status = SwapStatus.ACCEPTED if accept else SwapStatus.REJECTED
    swap.responded_at = now_local()
    db.commit()     # the ORM notices the changed fields and writes an UPDATE (like Hibernate dirty checking)
    return SwapRequestDto.of(swap)


def cancel_swap(db: DbSession, me: User, swap_id: int) -> SwapRequestDto:
    swap = _find_swap(db, swap_id)
    if swap.from_user_id != me.id:
        raise ApiError.forbidden("Only the sender can cancel this request.")
    _require_pending(swap)
    swap.status = SwapStatus.CANCELLED
    swap.responded_at = now_local()
    db.commit()
    return SwapRequestDto.of(swap)


def _find_swap(db: DbSession, swap_id: int) -> SwapRequest:
    swap = db.scalar(_swap_query().where(SwapRequest.id == swap_id))
    if swap is None:
        raise ApiError.not_found("Swap request not found.")
    return swap


def _require_pending(swap: SwapRequest) -> None:
    if swap.status != SwapStatus.PENDING:
        raise ApiError.conflict(f"This request was already {swap.status.value.lower()}.")


# ============================================================ sessions
ROOM_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"   # no 0/o, 1/l/i: easy to read aloud


def _session_query():
    return select(Session).options(joinedload(Session.teacher), joinedload(Session.learner))


def create_session(db: DbSession, me: User, req: SessionCreate) -> SessionDto:
    swap = _find_swap(db, req.swap_request_id)
    is_sender, is_receiver = swap.from_user_id == me.id, swap.to_user_id == me.id
    if not is_sender and not is_receiver:
        raise ApiError.forbidden("You are not part of this swap.")
    if swap.status != SwapStatus.ACCEPTED:
        raise ApiError.bad_request("Sessions can only be scheduled for accepted swaps.")
    scheduled_at = req.scheduled_at.replace(tzinfo=None)
    if scheduled_at < now_local() - timedelta(minutes=5):
        raise ApiError.bad_request("Choose a date and time in the future.")

    me_entity = swap.from_user if is_sender else swap.to_user
    partner = swap.to_user if is_sender else swap.from_user
    topic = _clean(req.skill_topic) or _default_topic(swap, req.i_am_teacher, is_sender)

    session = Session(
        teacher=me_entity if req.i_am_teacher else partner,
        learner=partner if req.i_am_teacher else me_entity,
        swap_request_id=swap.id, skill_topic=topic, scheduled_at=scheduled_at,
        duration_minutes=req.duration_minutes,
        meeting_link="https://meet.jit.si/SkillSwap-" + "".join(secrets.choice(ROOM_CHARS) for _ in range(12)),
    )
    db.add(session)
    db.commit()
    return SessionDto.of(session, me.id, False)


def _default_topic(swap: SwapRequest, i_am_teacher: bool, is_sender: bool) -> str:
    """The sender asked to learn swap.skill_name and offered swap.offered_skill_name in return."""
    sender_learns = is_sender != i_am_teacher
    if sender_learns or not swap.offered_skill_name:
        return swap.skill_name
    return swap.offered_skill_name


def my_sessions(db: DbSession, me: User) -> list[SessionDto]:
    rated = set(db.scalars(select(Rating.session_id).where(Rating.from_user_id == me.id)).all())
    rows = db.scalars(_session_query().where(or_(Session.teacher_id == me.id, Session.learner_id == me.id))
                      .order_by(Session.scheduled_at.desc())).all()
    return [SessionDto.of(s, me.id, s.id in rated) for s in rows]


def update_session_status(db: DbSession, me: User, session_id: int, new_status: SessionStatus) -> SessionDto:
    session = db.scalar(_session_query().where(Session.id == session_id))
    if session is None:
        raise ApiError.not_found("Session not found.")
    if me.id not in (session.teacher_id, session.learner_id):
        raise ApiError.forbidden("You are not part of this session.")
    if session.status != SessionStatus.SCHEDULED:
        raise ApiError.conflict(f"This session is already {session.status.value.lower()}.")
    session.status = new_status
    db.commit()
    return SessionDto.of(session, me.id, False)


# ============================================================ ratings
def rate(db: DbSession, me: User, req: RatingCreate) -> RatingDto:
    session = db.scalar(_session_query().where(Session.id == req.session_id))
    if session is None:
        raise ApiError.not_found("Session not found.")
    is_teacher, is_learner = session.teacher_id == me.id, session.learner_id == me.id
    if not is_teacher and not is_learner:
        raise ApiError.forbidden("You can only rate sessions you took part in.")
    if session.status != SessionStatus.COMPLETED:
        raise ApiError.bad_request("Mark the session as completed before rating it.")
    if db.scalar(select(Rating.id).where(Rating.session_id == session.id, Rating.from_user_id == me.id)):
        raise ApiError.conflict("You already rated this session.")

    from_user = session.teacher if is_teacher else session.learner
    to_user = session.learner if is_teacher else session.teacher
    rating = Rating(session=session, from_user=from_user, to_user=to_user,
                    score=req.score, comment=_clean(req.comment))
    db.add(rating)

    # Running average stored on the user: no need to re-read all their ratings.
    count, average = to_user.rating_count or 0, to_user.rating or 0.0
    to_user.rating = round((average * count + req.score) / (count + 1), 2)
    to_user.rating_count = count + 1
    db.commit()
    return RatingDto.of(rating)


def ratings_received(db: DbSession, user_id: int) -> list[RatingDto]:
    rows = db.scalars(select(Rating)
                      .options(joinedload(Rating.from_user), joinedload(Rating.session))
                      .where(Rating.to_user_id == user_id)
                      .order_by(Rating.created_at.desc())).all()
    return [RatingDto.of(r) for r in rows]


# ============================================================ dashboard
def dashboard(db: DbSession, me: User) -> DashboardDto:
    skills = my_skills(db, me)
    pending = [r for r in incoming_swaps(db, me) if r.status == "PENDING"][:5]
    cutoff = now_local() - timedelta(hours=1)
    upcoming = sorted((s for s in my_sessions(db, me) if s.status == "SCHEDULED" and s.scheduled_at >= cutoff),
                      key=lambda s: s.scheduled_at)

    pending_count = db.scalar(select(func.count(SwapRequest.id)).where(
        SwapRequest.to_user_id == me.id, SwapRequest.status == SwapStatus.PENDING))
    active_swaps = db.scalar(select(func.count(SwapRequest.id)).where(
        SwapRequest.status == SwapStatus.ACCEPTED,
        or_(SwapRequest.from_user_id == me.id, SwapRequest.to_user_id == me.id)))

    return DashboardDto(
        skills_listed=len(skills), pending_requests=pending_count, active_swaps=active_swaps,
        rating=me.rating or 0.0, rating_count=me.rating_count or 0, upcoming_sessions=len(upcoming),
        my_skills=skills, incoming_requests=pending, next_sessions=upcoming[:3],
        top_matches=matching.matches_for(db, me, 3),
    )


# ============================================================ admin
def admin_stats(db: DbSession) -> AdminStatsDto:
    count = lambda stmt: db.scalar(stmt) or 0   # noqa: E731
    return AdminStatsDto(
        users=count(select(func.count(User.id)).where(User.role == Role.USER)),
        active_users=count(select(func.count(User.id)).where(User.role == Role.USER, User.active.is_(True))),
        skills=count(select(func.count(Skill.id))),
        verified_skills=count(select(func.count(Skill.id)).where(Skill.verified.is_(True))),
        swap_requests=count(select(func.count(SwapRequest.id))),
        sessions=count(select(func.count(Session.id))),
        completed_sessions=count(select(func.count(Session.id)).where(Session.status == SessionStatus.COMPLETED)),
        skill_tests=count(select(func.count(SkillTest.id))),
    )


def admin_users(db: DbSession) -> list[UserDto]:
    return [UserDto.of(u) for u in db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc()))]


def admin_sessions(db: DbSession) -> list[SessionDto]:
    rows = db.scalars(_session_query().order_by(Session.scheduled_at.desc())).all()
    return [SessionDto.of(s, None, False) for s in rows]


def admin_set_active(db: DbSession, admin: User, user_id: int, active: bool) -> UserDto:
    user = _admin_target(db, admin, user_id)
    user.active = active     # takes effect at once: login, token check and matching all read this flag
    db.commit()
    return UserDto.of(user)


def admin_delete(db: DbSession, admin: User, user_id: int) -> None:
    user = _admin_target(db, admin, user_id)
    uid = user.id
    # Remove rows that point at the user first (foreign keys), in a safe order, in ONE transaction.
    user_sessions = select(Session.id).where(or_(Session.teacher_id == uid, Session.learner_id == uid))
    user_swaps = select(SwapRequest.id).where(or_(SwapRequest.from_user_id == uid, SwapRequest.to_user_id == uid))
    user_tests = select(SkillTest.id).where(SkillTest.user_id == uid)
    db.execute(delete(Rating).where(or_(Rating.from_user_id == uid, Rating.to_user_id == uid,
                                        Rating.session_id.in_(user_sessions))))
    db.execute(delete(Session).where(or_(Session.teacher_id == uid, Session.learner_id == uid)))
    db.execute(update(Session).where(Session.swap_request_id.in_(user_swaps)).values(swap_request_id=None))
    db.execute(delete(SwapRequest).where(or_(SwapRequest.from_user_id == uid, SwapRequest.to_user_id == uid)))
    db.execute(delete(TestAnswer).where(TestAnswer.test_id.in_(user_tests)))
    db.execute(delete(SkillTest).where(SkillTest.user_id == uid))
    db.delete(user)           # skills go with it (cascade)
    db.commit()


def _admin_target(db: DbSession, admin: User, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError.not_found("User not found.")
    if user.id == admin.id:
        raise ApiError.bad_request("You can't change your own admin account here.")
    if user.role == Role.ADMIN:
        raise ApiError.forbidden("Admin accounts can't be suspended or deleted.")
    return user

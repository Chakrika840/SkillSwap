"""
Smart Matching Algorithm.

For the current user (me) and every other active user (them):
  teaches_me     = their OFFERED skills that match my WANTED skills
  learns_from_me = their WANTED skills that match my OFFERED skills

Score (0-100):
  +35       they can teach me something I want
  +35       they want to learn something I teach (two-way barter)
  +3/6/10   level of the best skill they can teach me (Beginner/Intermediate/Advanced)
  +10       one of those skills is AI-verified
  +0..10    their average rating x 2
  +5        same city
"""
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, joinedload

from ..models import ProficiencyLevel, Role, Skill, SkillType, User
from ..schemas import SkillDto, UserCardDto

LEVEL_POINTS = {ProficiencyLevel.ADVANCED: 10, ProficiencyLevel.INTERMEDIATE: 6, ProficiencyLevel.BEGINNER: 3}


def normalize(name: str | None) -> str:
    """'  React   JS ' -> 'react js' so names compare fairly."""
    return " ".join((name or "").lower().split())


def matches_for(db: DbSession, me: User, limit: int) -> list[UserCardDto]:
    by_user = _skills_by_user(db)
    mine = by_user.get(me.id, (None, []))[1]
    cards = [
        _build_card(them, skills, mine, me)
        for user_id, (them, skills) in by_user.items()
        if user_id != me.id
    ]
    cards = [c for c in cards if c.match_score is not None]
    # Best score first, then best rating (sorted() is stable, like Java's).
    cards.sort(key=lambda c: (-c.match_score, -c.rating))
    return cards[:limit]


def search(db: DbSession, me: User, query: str) -> list[UserCardDto]:
    """Users who teach a skill whose name contains the query. Verified teachers first, then by rating."""
    q = normalize(query)
    by_user = _skills_by_user(db)
    mine = by_user.get(me.id, (None, []))[1]

    def teaches_query(skill: Skill) -> bool:
        return skill.type == SkillType.OFFERED and q in normalize(skill.name)

    found = [
        (them, skills) for user_id, (them, skills) in by_user.items()
        if user_id != me.id and (not q or any(teaches_query(s) for s in skills))
    ]
    found.sort(key=lambda e: (
        not any(s.verified and teaches_query(s) for s in e[1]),   # verified first
        -(e[0].rating or 0),                                       # then higher rating
    ))
    return [_build_card(them, skills, mine, me) for them, skills in found[:50]]


# ------------------------------------------------------------------ helpers
def _skills_by_user(db: DbSession) -> dict[int, tuple[User, list[Skill]]]:
    """ONE query loads every skill of every active normal user together with the user
    (joinedload = SQL JOIN, avoiding the N+1 problem). Then group skills by user."""
    skills = db.scalars(
        select(Skill)
        .join(Skill.user)
        .where(User.active.is_(True), User.role == Role.USER)
        .options(joinedload(Skill.user))
        .order_by(Skill.id)
    ).all()
    grouped: dict[int, tuple[User, list[Skill]]] = {}
    for skill in skills:
        grouped.setdefault(skill.user_id, (skill.user, []))[1].append(skill)
    return grouped


def _build_card(them: User, their_skills: list[Skill], mine: list[Skill], me: User) -> UserCardDto:
    my_wanted = {normalize(s.name) for s in mine if s.type == SkillType.WANTED}
    my_offered = {normalize(s.name) for s in mine if s.type == SkillType.OFFERED}

    teaches_me = sorted(
        (s for s in their_skills if s.type == SkillType.OFFERED and normalize(s.name) in my_wanted),
        key=lambda s: s.level.rank, reverse=True,                     # best level first
    )
    learns_from_me = [s for s in their_skills if s.type == SkillType.WANTED and normalize(s.name) in my_offered]

    score = None
    reasons: list[str] = []
    if teaches_me or learns_from_me:
        total = 0
        if teaches_me:
            total += 35
            total += LEVEL_POINTS[teaches_me[0].level]
            if any(s.verified for s in teaches_me):
                total += 10
            reasons.append("Can teach you " + _join_names(teaches_me))
        if learns_from_me:
            total += 35
            reasons.append("Wants to learn " + _join_names(learns_from_me) + ", which you teach")
        if teaches_me and learns_from_me:
            reasons.insert(0, "You can teach each other")
        rating = them.rating or 0.0
        if rating > 0:
            total += int(min(10.0, rating * 2) + 0.5)      # round half up, like Java's Math.round
            count = them.rating_count or 0
            reasons.append(f"Rated {rating:.1f} by {count} learner{'' if count == 1 else 's'}")
        if me.city and them.city and me.city.strip().lower() == them.city.strip().lower():
            total += 5
            reasons.append("Also in " + them.city.strip())
        score = min(100, total)

    return UserCardDto(
        id=them.id, name=them.name, city=them.city, bio=them.bio,
        rating=them.rating or 0.0, rating_count=them.rating_count or 0,
        teaches=[SkillDto.of(s) for s in their_skills if s.type == SkillType.OFFERED],
        wants_to_learn=[SkillDto.of(s) for s in their_skills if s.type == SkillType.WANTED],
        match_score=score, match_reasons=reasons,
    )


def _join_names(skills: list[Skill]) -> str:
    names = list(dict.fromkeys(s.name for s in skills))[:3]     # distinct, keep order, max 3
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]

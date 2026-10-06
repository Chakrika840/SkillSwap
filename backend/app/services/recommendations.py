"""
"AI Picks": asks the trained model which skills to learn next, then finds SkillSwap users who teach them.
If the model can't help (no skills yet, or it fails to load), it falls back to the most-offered
skills on the platform, so the page always shows something useful (graceful degradation).
"""
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession, joinedload

from ..ml.recommender import get_recommender
from ..models import Skill, SkillType, User
from ..schemas import RecommendationDto, TeacherDto

log = logging.getLogger("skillswap.recommendations")
LIMIT = 8


def recommend(db: DbSession, me: User) -> list[RecommendationDto]:
    mine = db.scalars(select(Skill).where(Skill.user_id == me.id)).all()
    offered = [s.name for s in mine if s.type == SkillType.OFFERED]
    wanted = [s.name for s in mine if s.type == SkillType.WANTED]
    exclude = [s.name for s in mine]

    picks: list[tuple[str, float]] = []
    source = "ML model"
    if offered or wanted:
        try:
            picks, how = get_recommender().recommend(offered, wanted, exclude, LIMIT)
            if how == "popular":
                source = "Popular among learners"   # model had no data on these skills
        except Exception as exc:                      # model file missing/corrupt: don't break the page
            log.warning("Recommendation model unavailable: %s", exc)
            picks = []
    if not picks:
        picks = _popular_skills(db, exclude)
        source = "Popular on SkillSwap"

    result = []
    for skill_name, score in picks:
        teachers = db.scalars(
            select(Skill).join(Skill.user).options(joinedload(Skill.user))
            .where(Skill.type == SkillType.OFFERED, func.lower(Skill.name) == skill_name.lower(),
                   User.active.is_(True), User.id != me.id)
            .order_by(Skill.verified.desc(), User.rating.desc())
            .limit(3)
        ).all()
        result.append(RecommendationDto(
            skill=skill_name,
            score=int(score * 100 + 0.5),
            source=source,
            teachers=[TeacherDto(user_id=t.user.id, name=t.user.name, rating=t.user.rating or 0.0,
                                 level=t.level.value, verified=t.verified) for t in teachers],
        ))
    return result


def _popular_skills(db: DbSession, exclude: list[str]) -> list[tuple[str, float]]:
    """Most-offered skill names on SkillSwap, scored 0-1 against the most popular one."""
    skip = {name.lower() for name in exclude}
    rows = db.execute(
        select(func.lower(Skill.name), func.count(Skill.id))
        .where(Skill.type == SkillType.OFFERED)
        .group_by(func.lower(Skill.name))
        .order_by(func.count(Skill.id).desc())
    ).all()
    if not rows:
        return []
    top = max(1, rows[0][1])
    out = []
    for name, count in rows:
        if name in skip:
            continue
        out.append((name[:1].upper() + name[1:], count / top))
        if len(out) == LIMIT:
            break
    return out

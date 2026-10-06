"""
Database tables as SQLAlchemy models (the Python equivalent of JPA @Entity classes).
Enums are stored as text ("ADMIN", not 1), like @Enumerated(EnumType.STRING).
"""
import enum
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .timeutil import now_local, now_utc


# ------------------------------------------------------------------ enums
class Role(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class SkillType(str, enum.Enum):
    OFFERED = "OFFERED"   # a skill the user can teach
    WANTED = "WANTED"     # a skill the user wants to learn


class ProficiencyLevel(str, enum.Enum):
    # Order matters: the skill test steps one level down using the position in this list.
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"

    @property
    def rank(self) -> int:
        return list(ProficiencyLevel).index(self)


class SwapStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class SessionStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TestStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    PASSED = "PASSED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


def _enum(cls, length: int = 20):
    return Enum(cls, native_enum=False, length=length, validate_strings=True)


# ------------------------------------------------------------------ tables
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(100))            # bcrypt hash, never the real password
    role: Mapped[Role] = mapped_column(_enum(Role, 10), default=Role.USER)
    city: Mapped[str | None] = mapped_column(String(80))
    bio: Mapped[str | None] = mapped_column(String(500))
    rating: Mapped[float] = mapped_column(Float, default=0.0)      # average stars received
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)    # False = suspended by an admin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    # One user has many skills; deleting the user deletes their skills.
    skills: Mapped[list["Skill"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    level: Mapped[ProficiencyLevel] = mapped_column(_enum(ProficiencyLevel))
    type: Mapped[SkillType] = mapped_column(_enum(SkillType, 10), default=SkillType.OFFERED)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # AI skill verification
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_level: Mapped[ProficiencyLevel | None] = mapped_column(_enum(ProficiencyLevel))
    verification_score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    user: Mapped[User] = relationship(back_populates="skills")


class SwapRequest(Base):
    """'I want to learn X from you (and can teach you Y)'. Skill names are stored as text
    so a request still makes sense if a skill is deleted later."""
    __tablename__ = "swap_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    skill_name: Mapped[str] = mapped_column(String(60))
    skill_level: Mapped[ProficiencyLevel | None] = mapped_column(_enum(ProficiencyLevel))
    offered_skill_name: Mapped[str | None] = mapped_column(String(60))
    message: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[SwapStatus] = mapped_column(_enum(SwapStatus, 12), default=SwapStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime)

    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped[User] = relationship(foreign_keys=[to_user_id])


class Session(Base):
    """A scheduled learning session created from an accepted swap request."""
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    swap_request_id: Mapped[int | None] = mapped_column(ForeignKey("swap_requests.id"))
    skill_topic: Mapped[str] = mapped_column(String(100))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[SessionStatus] = mapped_column(_enum(SessionStatus, 12), default=SessionStatus.SCHEDULED)
    meeting_link: Mapped[str] = mapped_column(String(200))         # free Jitsi Meet room
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    teacher: Mapped[User] = relationship(foreign_keys=[teacher_id])
    learner: Mapped[User] = relationship(foreign_keys=[learner_id])
    swap_request: Mapped[SwapRequest | None] = relationship()


class Rating(Base):
    __tablename__ = "ratings"
    # The database itself refuses a second rating by the same person for the same session.
    __table_args__ = (UniqueConstraint("session_id", "from_user_id", name="uk_rating_session_from"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    score: Mapped[int] = mapped_column(Integer)                     # 1 to 5 stars
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    session: Mapped[Session] = relationship()
    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped[User] = relationship(foreign_keys=[to_user_id])


# ------------------------------------------------------------------ AI skill test
class TestQuestion(Base):
    """Shared question bank: AI-generated questions are stored and reused across tests."""
    __tablename__ = "test_question"
    __table_args__ = (Index("idx_test_question_skill_level", "skill_key", "level"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_key: Mapped[str] = mapped_column(String(60))              # normalised name, e.g. "python"
    level: Mapped[ProficiencyLevel] = mapped_column(_enum(ProficiencyLevel))
    question: Mapped[str] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text)                 # JSON list of exactly 4 options
    correct_index: Mapped[int] = mapped_column(Integer)             # 0-3, never sent to the browser
    explanation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class SkillTest(Base):
    """One attempt by one user to verify one of their skills. Times are UTC."""
    __tablename__ = "skill_test"
    __table_args__ = (Index("idx_skill_test_user_skill", "user_id", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    skill_id: Mapped[int] = mapped_column(Integer)
    skill_name: Mapped[str] = mapped_column(String(100))
    claimed_level: Mapped[ProficiencyLevel] = mapped_column(_enum(ProficiencyLevel))
    status: Mapped[TestStatus] = mapped_column(_enum(TestStatus))
    score: Mapped[int | None] = mapped_column(Integer)              # 0-100, set on submit
    correct_count: Mapped[int | None] = mapped_column(Integer)
    total_questions: Mapped[int] = mapped_column(Integer)
    verified_level: Mapped[ProficiencyLevel | None] = mapped_column(_enum(ProficiencyLevel))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)

    answers: Mapped[list["TestAnswer"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="TestAnswer.position")


class TestAnswer(Base):
    """A question placed in a test, plus the user's answer once submitted."""
    __tablename__ = "test_answer"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("skill_test.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("test_question.id"))
    position: Mapped[int] = mapped_column(Integer)                  # 1-10
    option_order: Mapped[str] = mapped_column(String(20))           # shuffled order shown, e.g. "2,0,3,1"
    selected_index: Mapped[int | None] = mapped_column(Integer)     # original index picked (0-3)
    correct: Mapped[bool | None] = mapped_column(Boolean)

    test: Mapped[SkillTest] = relationship(back_populates="answers")
    question: Mapped[TestQuestion] = relationship()

"""
Request and response shapes (Pydantic models) = the DTOs of the Spring Boot version.

Python fields are snake_case; the JSON uses camelCase (to_camel alias generator), so the
React frontend receives exactly the same field names as before, e.g. rating_count -> ratingCount.
Pydantic also validates every request body, like @Valid + @NotBlank/@Size in Spring.
"""
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints
from pydantic.alias_generators import to_camel

from .models import ProficiencyLevel, Rating, Session, Skill, SkillType, SwapRequest, User


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def Text(max_length: int, min_length: int = 1):
    """A required string, trimmed, with length limits (like @NotBlank @Size(max = ...))."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)]


OptionalText = lambda max_length: Optional[Annotated[str, StringConstraints(max_length=max_length)]]  # noqa: E731


# ============================================================ requests
class RegisterRequest(CamelModel):
    name: Text(80)
    email: Annotated[EmailStr, StringConstraints(max_length=120)]
    password: Annotated[str, StringConstraints(min_length=6, max_length=100)]


class LoginRequest(CamelModel):
    email: Text(120)
    password: Annotated[str, StringConstraints(min_length=1)]


class UpdateProfileRequest(CamelModel):
    name: Text(80)
    city: OptionalText(80) = None
    bio: OptionalText(500) = None


class SkillRequest(CamelModel):
    name: Text(60)
    level: ProficiencyLevel
    type: SkillType


class SwapRequestCreate(CamelModel):
    to_user_id: int
    skill_name: Text(60)
    offered_skill_name: OptionalText(60) = None
    message: OptionalText(500) = None


class SessionCreate(CamelModel):
    swap_request_id: int
    skill_topic: OptionalText(100) = None
    scheduled_at: datetime
    duration_minutes: int = Field(ge=15, le=240)
    i_am_teacher: bool = False


class RatingCreate(CamelModel):
    session_id: int
    score: int = Field(ge=1, le=5)
    comment: OptionalText(500) = None


class UserStatusRequest(CamelModel):
    active: bool


# ============================================================ responses
class UserDto(CamelModel):
    id: int
    name: str
    email: str
    role: str
    city: Optional[str]
    bio: Optional[str]
    rating: float
    rating_count: int
    active: bool
    created_at: datetime

    @classmethod
    def of(cls, u: User) -> "UserDto":
        # Copies everything EXCEPT the password hash.
        return cls(id=u.id, name=u.name, email=u.email, role=u.role.value, city=u.city, bio=u.bio,
                   rating=u.rating or 0.0, rating_count=u.rating_count or 0, active=u.active,
                   created_at=u.created_at)


class AuthResponse(CamelModel):
    token: str
    user: UserDto


class UserSummary(CamelModel):
    id: int
    name: str
    email: str
    rating: float

    @classmethod
    def of(cls, u: User) -> "UserSummary":
        return cls(id=u.id, name=u.name, email=u.email, rating=u.rating or 0.0)


class SkillDto(CamelModel):
    id: int
    name: str
    level: str
    type: str
    verified: bool
    verified_level: Optional[str]
    verification_score: Optional[int]

    @classmethod
    def of(cls, s: Skill) -> "SkillDto":
        return cls(id=s.id, name=s.name, level=s.level.value, type=s.type.value, verified=s.verified,
                   verified_level=s.verified_level.value if s.verified_level else None,
                   verification_score=s.verification_score)


class UserCardDto(CamelModel):
    """A user as shown on Explore / match cards. match_score is 0-100, or None when not a match."""
    id: int
    name: str
    city: Optional[str]
    bio: Optional[str]
    rating: float
    rating_count: int
    teaches: list[SkillDto]
    wants_to_learn: list[SkillDto]
    match_score: Optional[int]
    match_reasons: list[str]


class SwapRequestDto(CamelModel):
    id: int
    from_user: UserSummary
    to_user: UserSummary
    skill_name: str
    skill_level: Optional[str]
    offered_skill_name: Optional[str]
    message: Optional[str]
    status: str
    created_at: datetime
    responded_at: Optional[datetime]

    @classmethod
    def of(cls, r: SwapRequest) -> "SwapRequestDto":
        return cls(id=r.id, from_user=UserSummary.of(r.from_user), to_user=UserSummary.of(r.to_user),
                   skill_name=r.skill_name, skill_level=r.skill_level.value if r.skill_level else None,
                   offered_skill_name=r.offered_skill_name, message=r.message, status=r.status.value,
                   created_at=r.created_at, responded_at=r.responded_at)


class SessionDto(CamelModel):
    id: int
    teacher: UserSummary
    learner: UserSummary
    skill_topic: str
    scheduled_at: datetime
    duration_minutes: int
    status: str
    meeting_link: str
    my_role: Optional[str]          # "TEACHER" / "LEARNER" from the viewer's point of view
    rated_by_me: bool

    @classmethod
    def of(cls, s: Session, viewer_id: Optional[int], rated_by_me: bool) -> "SessionDto":
        role = None if viewer_id is None else ("TEACHER" if s.teacher_id == viewer_id else "LEARNER")
        return cls(id=s.id, teacher=UserSummary.of(s.teacher), learner=UserSummary.of(s.learner),
                   skill_topic=s.skill_topic, scheduled_at=s.scheduled_at, duration_minutes=s.duration_minutes,
                   status=s.status.value, meeting_link=s.meeting_link, my_role=role, rated_by_me=rated_by_me)


class RatingDto(CamelModel):
    id: int
    from_name: str
    score: int
    comment: Optional[str]
    skill_topic: str
    created_at: datetime

    @classmethod
    def of(cls, r: Rating) -> "RatingDto":
        return cls(id=r.id, from_name=r.from_user.name, score=r.score, comment=r.comment,
                   skill_topic=r.session.skill_topic, created_at=r.created_at)


class DashboardDto(CamelModel):
    skills_listed: int
    pending_requests: int
    active_swaps: int
    rating: float
    rating_count: int
    upcoming_sessions: int
    my_skills: list[SkillDto]
    incoming_requests: list[SwapRequestDto]
    next_sessions: list[SessionDto]
    top_matches: list[UserCardDto]


class AdminStatsDto(CamelModel):
    users: int
    active_users: int
    skills: int
    verified_skills: int
    swap_requests: int
    sessions: int
    completed_sessions: int
    skill_tests: int


class TeacherDto(CamelModel):
    user_id: int
    name: str
    rating: float
    level: str
    verified: bool


class RecommendationDto(CamelModel):
    skill: str
    score: int                      # 0-100, relative to the best pick
    source: str                     # "ML model" or a fallback label
    teachers: list[TeacherDto]


# ============================================================ AI skill test
class AnswerSubmission(CamelModel):
    question_id: Optional[int] = None
    selected_key: Optional[int] = None


class SubmitTestRequest(CamelModel):
    answers: list[AnswerSubmission] = []


class OptionView(CamelModel):
    key: int                        # the option's ORIGINAL index; sent back as the answer
    text: str


class QuestionView(CamelModel):
    """A question as the test-taker sees it: options shuffled, no correct answer."""
    question_id: int
    position: int
    question: str
    options: list[OptionView]


class SkillTestStatusResponse(CamelModel):
    skill_id: int
    skill_name: str
    level: str
    verified: bool
    verified_level: Optional[str]
    verification_score: Optional[int]
    test_in_progress: bool
    seconds_remaining: int
    retry_available_at: Optional[str]
    can_start: bool
    questions_per_test: int
    duration_seconds: int
    pass_score: int
    partial_score: int


class StartTestResponse(CamelModel):
    test_id: int
    skill_id: int
    skill_name: str
    level: str
    total_questions: int
    duration_seconds: int
    seconds_remaining: int
    expires_at: str
    questions: list[QuestionView]


class ReviewItem(CamelModel):
    """Shown only after submission; options in their original order."""
    position: int
    question: str
    options: list[str]
    selected_index: Optional[int]
    correct_index: int
    correct: bool
    explanation: Optional[str]


class TestResultResponse(CamelModel):
    test_id: int
    skill_id: int
    skill_name: str
    claimed_level: str
    status: str
    score: int
    correct_count: int
    total_questions: int
    verified_level: Optional[str]
    retry_available_at: Optional[str]
    review: list[ReviewItem]

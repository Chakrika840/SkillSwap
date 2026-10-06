"""
REST endpoints for accounts, users, skills, swap requests, sessions, ratings and admin.
Each endpoint: validate input (Pydantic) -> get the logged-in user (Depends) -> call a service.
URLs and JSON are identical to the Spring Boot version, so the React app works unchanged.
"""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..models import SessionStatus, User
from ..schemas import (AdminStatsDto, AuthResponse, DashboardDto, LoginRequest, RatingCreate, RatingDto,
                       RecommendationDto, RegisterRequest, SessionCreate, SessionDto, SkillDto, SkillRequest,
                       SwapRequestCreate, SwapRequestDto, UpdateProfileRequest, UserCardDto, UserDto,
                       UserStatusRequest)
from ..security import get_current_user, require_admin
from ..services import core, matching, recommendations

# ------------------------------------------------------------------ public
auth = APIRouter(prefix="/api/auth", tags=["auth"])


@auth.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: DbSession = Depends(get_db)):
    return core.register(db, req)


@auth.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: DbSession = Depends(get_db)):
    return core.login(db, req)


# ------------------------------------------------------------------ users, matching, dashboard
users = APIRouter(prefix="/api", tags=["users"])


@users.get("/health")
def health():
    return {"status": "ok", "service": "skillswap-backend"}


@users.get("/users/me", response_model=UserDto)
def me(user: User = Depends(get_current_user)):
    return UserDto.of(user)


@users.put("/users/me", response_model=UserDto)
def update_me(req: UpdateProfileRequest, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.update_profile(db, user, req)


@users.get("/users/search", response_model=list[UserCardDto])
def search(skill: str = "", user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """Explore: users who teach a skill matching ?skill=... (everyone if empty)."""
    return matching.search(db, user, skill)


@users.get("/matches", response_model=list[UserCardDto])
def matches(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """Smart matching: the 20 best learning partners."""
    return matching.matches_for(db, user, 20)


@users.get("/users/{user_id}/ratings", response_model=list[RatingDto])
def ratings_of(user_id: int, _: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.ratings_received(db, user_id)


@users.get("/dashboard", response_model=DashboardDto)
def dashboard(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.dashboard(db, user)


@users.get("/recommendations", response_model=list[RecommendationDto])
def ai_picks(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """AI Picks: skills to learn next from the ML model, plus people who teach them."""
    return recommendations.recommend(db, user)


# ------------------------------------------------------------------ skills
skills = APIRouter(prefix="/api/skills", tags=["skills"])


@skills.get("/me", response_model=list[SkillDto])
def my_skills(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.my_skills(db, user)


@skills.post("", response_model=SkillDto, status_code=status.HTTP_201_CREATED)
def add_skill(req: SkillRequest, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.add_skill(db, user, req)


@skills.put("/{skill_id}", response_model=SkillDto)
def update_skill(skill_id: int, req: SkillRequest, user: User = Depends(get_current_user),
                 db: DbSession = Depends(get_db)):
    return core.update_skill(db, user, skill_id, req)


@skills.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    core.delete_skill(db, user, skill_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ swap requests
swaps = APIRouter(prefix="/api/swap-requests", tags=["swap requests"])


@swaps.post("", response_model=SwapRequestDto, status_code=status.HTTP_201_CREATED)
def create_swap(req: SwapRequestCreate, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.create_swap(db, user, req)


@swaps.get("/incoming", response_model=list[SwapRequestDto])
def incoming(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.incoming_swaps(db, user)


@swaps.get("/outgoing", response_model=list[SwapRequestDto])
def outgoing(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.outgoing_swaps(db, user)


@swaps.get("/accepted", response_model=list[SwapRequestDto])
def accepted(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """Accepted swaps the user can schedule sessions for."""
    return core.accepted_swaps(db, user)


@swaps.put("/{swap_id}/accept", response_model=SwapRequestDto)
def accept(swap_id: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.respond_swap(db, user, swap_id, True)


@swaps.put("/{swap_id}/reject", response_model=SwapRequestDto)
def reject(swap_id: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.respond_swap(db, user, swap_id, False)


@swaps.put("/{swap_id}/cancel", response_model=SwapRequestDto)
def cancel_swap(swap_id: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.cancel_swap(db, user, swap_id)


# ------------------------------------------------------------------ sessions and ratings
sessions = APIRouter(prefix="/api/sessions", tags=["sessions"])


@sessions.post("", response_model=SessionDto, status_code=status.HTTP_201_CREATED)
def create_session(req: SessionCreate, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.create_session(db, user, req)


@sessions.get("/me", response_model=list[SessionDto])
def my_sessions(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.my_sessions(db, user)


@sessions.put("/{session_id}/complete", response_model=SessionDto)
def complete(session_id: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.update_session_status(db, user, session_id, SessionStatus.COMPLETED)


@sessions.put("/{session_id}/cancel", response_model=SessionDto)
def cancel_session(session_id: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.update_session_status(db, user, session_id, SessionStatus.CANCELLED)


ratings = APIRouter(prefix="/api/ratings", tags=["ratings"])


@ratings.post("", response_model=RatingDto, status_code=status.HTTP_201_CREATED)
def rate(req: RatingCreate, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return core.rate(db, user, req)


# ------------------------------------------------------------------ admin (ROLE ADMIN only)
admin = APIRouter(prefix="/api/admin", tags=["admin"])


@admin.get("/stats", response_model=AdminStatsDto)
def stats(_: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    return core.admin_stats(db)


@admin.get("/users", response_model=list[UserDto])
def all_users(_: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    return core.admin_users(db)


@admin.put("/users/{user_id}/status", response_model=UserDto)
def set_status(user_id: int, req: UserStatusRequest, me_admin: User = Depends(require_admin),
               db: DbSession = Depends(get_db)):
    return core.admin_set_active(db, me_admin, user_id, req.active)


@admin.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, me_admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    core.admin_delete(db, me_admin, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin.get("/sessions", response_model=list[SessionDto])
def all_sessions(_: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    return core.admin_sessions(db)


ROUTERS = [auth, users, skills, swaps, sessions, ratings, admin]

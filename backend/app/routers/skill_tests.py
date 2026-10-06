"""Endpoints for the AI skill verification test."""
from typing import Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..models import User
from ..schemas import SkillTestStatusResponse, StartTestResponse, SubmitTestRequest, TestResultResponse
from ..security import get_current_user
from ..services import skill_test

router = APIRouter(prefix="/api/skill-tests", tags=["skill tests"])


@router.get("/skills/{skill_id}/status", response_model=SkillTestStatusResponse)
def status(skill_id: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return skill_test.get_status(db, user, skill_id)


# A plain `def` (not async): FastAPI runs it in a worker thread, so the ~20 s AI call
# doesn't block other users' requests.
@router.post("/skills/{skill_id}/start", response_model=StartTestResponse)
def start(skill_id: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return skill_test.start_test(db, user, skill_id)


@router.post("/{test_id}/submit", response_model=TestResultResponse)
def submit(test_id: int, body: Optional[SubmitTestRequest] = Body(default=None),
           user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return skill_test.submit_test(db, user, test_id, body)


@router.get("/{test_id}/result", response_model=TestResultResponse)
def result(test_id: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return skill_test.get_result(db, user, test_id)

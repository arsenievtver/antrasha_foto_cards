import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserSession
from app.schemas.session import SessionCreateResponse

log = logging.getLogger("app.api.sessions")
router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreateResponse)
def create_session(db: Session = Depends(get_db)) -> SessionCreateResponse:
    s = UserSession()
    db.add(s)
    db.commit()
    db.refresh(s)
    log.info("POST /sessions new session_id=%s", s.id)
    return SessionCreateResponse(session_id=s.id)

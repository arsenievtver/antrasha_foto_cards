import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import require_user
from app.models import (
    FittingRequest,
    FittingRequestLikedPhoto,
    Interaction,
    Photo,
    User,
    UserRole,
    UserSession,
)
from app.schemas.auth import (
    AdminSuperuserLoginRequest,
    FittingRequestCreateRequest,
    FittingRequestCreateResponse,
    LoginRequest,
    MeOut,
    RegisterRequest,
    TokenResponse,
)
from app.security import create_access_token, hash_pin, verify_pin
from app.services.weights import merge_session_into_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=MeOut)
def me(current: User = Depends(require_user)) -> MeOut:
    return MeOut(
        id=current.id,
        phone=current.phone,
        display_name=current.display_name,
        role=current.role,
    )


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    session = db.get(UserSession, body.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found; create one via POST /sessions first",
        )
    phone = body.phone.strip()
    existing = db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone already registered",
        )

    user = User(
        phone=phone,
        display_name=body.display_name.strip(),
        pin_hash=hash_pin(body.pin),
        role=UserRole.user.value,
    )
    db.add(user)
    db.flush()
    merge_session_into_user(db, session_id=body.session_id, user=user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    phone = body.phone.strip()
    user = db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()
    if not user or not verify_pin(body.pin, user.pin_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone or PIN",
        )
    if user.role == UserRole.worker.value and not re.fullmatch(r"\d{6}", body.pin.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Worker PIN must be exactly 6 digits",
        )
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)


@router.post("/admin/superuser", response_model=TokenResponse)
def login_superuser(body: AdminSuperuserLoginRequest) -> TokenResponse:
    if not settings.admin_superuser_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Superuser login is not configured",
        )
    if body.username.strip() != settings.admin_superuser_username.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    ok = False
    if settings.admin_superuser_password_bcrypt and settings.admin_superuser_password_bcrypt.strip():
        ok = verify_pin(body.password, settings.admin_superuser_password_bcrypt.strip())
    elif settings.admin_superuser_password is not None:
        ok = secrets.compare_digest(
            body.password,
            settings.admin_superuser_password,
        )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(role="superuser")
    return TokenResponse(access_token=token, user_id=None, role="superuser")


@router.post("/fitting-request", response_model=FittingRequestCreateResponse)
def create_fitting_request(
    body: FittingRequestCreateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(require_user),
) -> FittingRequestCreateResponse:
    total = max(0, int(body.total or 0))
    likes = max(0, min(int(body.likes or 0), total if total > 0 else int(body.likes or 0)))
    match_rate = (likes / total) if total > 0 else 0.0
    note = body.note.strip() if body.note else None
    requested_photo_ids = []
    seen = set()
    for pid in body.photo_ids:
        if pid in seen:
            continue
        seen.add(pid)
        requested_photo_ids.append(pid)
    fr = FittingRequest(
        user_id=current.id,
        display_name=current.display_name,
        phone=current.phone,
        likes=likes,
        total=total,
        match_rate=match_rate,
        note=note,
        status="new",
    )
    db.add(fr)
    db.flush()
    if requested_photo_ids:
        liked_rows = db.scalars(
            select(Interaction.photo_id).where(
                Interaction.user_id == current.id,
                Interaction.action == "like",
                Interaction.photo_id.in_(requested_photo_ids),
            ),
        ).all()
        liked_ids = set(liked_rows)
        if liked_ids:
            photos = db.execute(
                select(Photo.id, Photo.url).where(Photo.id.in_(liked_ids)),
            ).all()
            for pid, purl in photos:
                db.add(
                    FittingRequestLikedPhoto(
                        request_id=fr.id,
                        photo_id=pid,
                        photo_url=purl,
                    ),
                )
    db.commit()
    db.refresh(fr)
    return FittingRequestCreateResponse(request_id=fr.id, status=fr.status)

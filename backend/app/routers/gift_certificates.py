import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AdminPrincipal, _bearer, get_admin_principal, require_permission
from app.models.gift_certificate import (
    GiftCertificate,
    GiftCertificateStatus,
    GiftCertificateTransaction,
    GiftTransactionStatus,
)
from app.schemas.gift_certificates import (
    GiftCertificateCreate,
    GiftCertificateOut,
    GiftCertificatePublicOut,
    GiftCertificateUpdate,
    GiftTransactionOut,
    TelegramSendBody,
)
from app.services.gift_certificates import (
    allocate_code,
    expire_open_transactions,
    generate_confirm_code,
    hide_name,
    hide_phone,
    new_ulid,
    send_confirm_sms,
    send_telegram,
    set_actual_status,
    telegram_text,
)
from app.config import settings

log = logging.getLogger("app.gift_certificates")

router = APIRouter(prefix="/gift-certificates", tags=["gift-certificates"])


def _out(cert: GiftCertificate) -> GiftCertificateOut:
    return GiftCertificateOut(
        id=cert.id,
        code=cert.code,
        nominal=cert.nominal,
        amount=cert.amount,
        description=cert.description,
        employee=cert.employee,
        check_amount=cert.check_amount,
        status=cert.status,
        created_at=cert.created_at,
        used_at=cert.used_at,
        indefinite=cert.indefinite,
        period=cert.period,
        name=cert.name,
        last_name=cert.last_name,
        phone=cert.phone,
    )


def _public_out(cert: GiftCertificate, *, full: bool) -> GiftCertificatePublicOut:
    transactions: list[GiftTransactionOut] = []
    if full:
        transactions = [
            GiftTransactionOut(
                time=tran.time,
                amount=tran.amount,
                sms_id=tran.sms_id,
                sms_sent=tran.sms_sent,
                sms_error=tran.sms_error,
                status=tran.status,
            )
            for tran in cert.transactions
        ]
    return GiftCertificatePublicOut(
        nominal=cert.nominal,
        amount=cert.amount,
        code=cert.code,
        description=cert.description,
        status=cert.status,
        created_at=cert.created_at,
        used_at=cert.used_at,
        indefinite=cert.indefinite,
        period=cert.period,
        name=cert.name if full else hide_name(cert.name),
        last_name=cert.last_name if full else hide_name(cert.last_name),
        phone=cert.phone if full else hide_phone(cert.phone),
        transactions=transactions,
    )


def _get_or_404(db: Session, cert_id: str) -> GiftCertificate:
    cert = db.get(GiftCertificate, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сертификат не найден")
    return cert


def _optional_principal(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AdminPrincipal | None:
    if credentials is None:
        return None
    try:
        return get_admin_principal(db, credentials)
    except HTTPException:
        return None


def _can_see_full(principal: AdminPrincipal | None) -> bool:
    return principal is not None and principal.has_permission("giftcards")


@router.get("/", response_model=list[GiftCertificateOut])
def list_certificates(
    db: Session = Depends(get_db),
    _: AdminPrincipal = Depends(require_permission("giftcards")),
) -> list[GiftCertificateOut]:
    certs = db.scalars(select(GiftCertificate).order_by(GiftCertificate.created_at.desc())).all()
    changed = False
    for cert in certs:
        if set_actual_status(cert):
            changed = True
    if changed:
        db.commit()
    return [_out(cert) for cert in certs]


@router.get("/{cert_id}", response_model=GiftCertificatePublicOut)
def get_certificate(
    cert_id: str,
    db: Session = Depends(get_db),
    principal: AdminPrincipal | None = Depends(_optional_principal),
) -> GiftCertificatePublicOut:
    cert = _get_or_404(db, cert_id)
    set_actual_status(cert)
    db.commit()
    db.refresh(cert)
    return _public_out(cert, full=_can_see_full(principal))


@router.post("/", response_model=GiftCertificateOut, status_code=status.HTTP_201_CREATED)
def create_certificate(
    body: GiftCertificateCreate,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_permission("giftcards")),
) -> GiftCertificateOut:
    if body.nominal < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Номинал не может быть отрицательным")
    phone = body.phone.strip()
    if not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите телефон")
    employee = body.employee.strip()
    if not employee:
        employee = (
            (principal.user.display_name or "").strip()
            if principal.user is not None
            else ""
        ) or "Сотрудник"
    status_value = body.status if body.status in {item.value for item in GiftCertificateStatus} else GiftCertificateStatus.ACTIVE.value
    cert = GiftCertificate(
        id=new_ulid(),
        code=allocate_code(db),
        nominal=body.nominal,
        amount=body.nominal,
        description=body.description or "",
        employee=employee,
        check_amount=body.check_amount,
        status=status_value,
        created_at=body.created_at or date.today(),
        indefinite=body.indefinite,
        period=None if body.indefinite else body.period,
        name=body.name,
        last_name=body.last_name,
        phone=phone,
    )
    set_actual_status(cert)
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return _out(cert)


@router.patch("/{cert_id}", response_model=GiftCertificateOut)
def update_certificate(
    cert_id: str,
    body: GiftCertificateUpdate,
    db: Session = Depends(get_db),
    _: AdminPrincipal = Depends(require_permission("giftcards")),
) -> GiftCertificateOut:
    cert = _get_or_404(db, cert_id)
    data = body.model_dump(exclude_unset=True)
    new_amount = data.pop("amount", None)
    if new_amount is not None:
        nominal = cert.nominal if cert.nominal is not None else new_amount
        if new_amount > nominal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Остаток не может быть больше номинала",
            )
        delta = new_amount - cert.amount
        cert.amount = new_amount
        if delta != 0:
            db.add(
                GiftCertificateTransaction(
                    cert_id=cert.id,
                    amount=delta,
                    status=GiftTransactionStatus.DONE.value,
                )
            )
    for field, value in data.items():
        setattr(cert, field, value)
    set_actual_status(cert)
    db.commit()
    db.refresh(cert)
    return _out(cert)


@router.post("/send-confirm-code/{cert_id}")
def send_confirm_code(
    cert_id: str,
    charge_sum: float = Query(...),
    db: Session = Depends(get_db),
    _: AdminPrincipal = Depends(require_permission("giftcards")),
) -> dict:
    cert = _get_or_404(db, cert_id)
    set_actual_status(cert)
    expire_open_transactions(db, cert)
    if cert.status != GiftCertificateStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Списать можно только действующий сертификат. Сейчас: {cert.status}",
        )
    if charge_sum <= 0 or charge_sum > cert.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сумма списания должна быть от 1 до остатка",
        )
    confirm_code = generate_confirm_code()
    tran = GiftCertificateTransaction(
        cert_id=cert.id,
        amount=-charge_sum,
        confirm_code=confirm_code,
        status=GiftTransactionStatus.OPENED.value,
    )
    db.add(tran)
    db.flush()
    cert.actual_tran_id = tran.id
    sms_id, sms_sent, sms_error = send_confirm_sms(cert, charge_sum, confirm_code)
    tran.sms_id = sms_id
    tran.sms_sent = sms_sent
    tran.sms_error = (sms_error or "")[:256] or None
    db.commit()
    payload: dict = {"result": "ok"}
    if not settings.mts_sms_enabled:
        payload["dev_confirm_code"] = confirm_code
    if sms_sent is False and sms_error:
        log.warning("SMS не ушла для %s: %s", cert.code, sms_error)
    return payload


@router.post("/charge/{cert_id}")
def charge_certificate(
    cert_id: str,
    confirm_code: str = Query(...),
    db: Session = Depends(get_db),
    _: AdminPrincipal = Depends(require_permission("giftcards")),
) -> dict:
    cert = _get_or_404(db, cert_id)
    set_actual_status(cert)
    expire_open_transactions(db, cert)
    if cert.status != GiftCertificateStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Списать можно только действующий сертификат. Сейчас: {cert.status}",
        )
    if not cert.actual_tran_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сначала отправьте код подтверждения")
    tran = db.get(GiftCertificateTransaction, cert.actual_tran_id)
    if tran is None or tran.cert_id != cert.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Активная операция не найдена")
    if tran.status in (GiftTransactionStatus.DONE.value, GiftTransactionStatus.CANCELLED.value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Код уже использован или истёк")
    if confirm_code.strip() != (tran.confirm_code or ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный код подтверждения")
    cert.amount = cert.amount + tran.amount
    tran.status = GiftTransactionStatus.DONE.value
    set_actual_status(cert)
    db.commit()
    return {"result": "ok", "amount": cert.amount, "status": cert.status}


@router.post("/send-telegram/{cert_id}")
def send_telegram_message(
    cert_id: str,
    body: TelegramSendBody,
    db: Session = Depends(get_db),
    _: AdminPrincipal = Depends(require_permission("giftcards")),
) -> dict:
    cert = _get_or_404(db, cert_id)
    set_actual_status(cert)
    db.commit()
    if cert.status != GiftCertificateStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сертификат не действует")
    try:
        send_telegram(body.chat_id, telegram_text(cert), body.image_url)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"result": "ok"}

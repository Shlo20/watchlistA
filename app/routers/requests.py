"""Restock request routes — the heart of the app."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.product import Product
from app.models.request import Request, RequestHistory, RequestStatus
from app.models.user import User, UserRole
from app.schemas.request import ArchiveStaleResponse, ClearAllResponse, DigestResponse, RequestCreate, RequestOut, RequestStatusUpdate
from app.services import notifications
from app.services.archive import archive_stale_pending_requests


router = APIRouter(prefix="/requests", tags=["requests"])


# Allowed status transitions. Anything not in this map is rejected.
VALID_TRANSITIONS = {
    RequestStatus.PENDING: {RequestStatus.DONE},
    RequestStatus.DONE: set(),
}


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.MANAGER)),
):
    """Manager creates a restock request. Buyers receive a daily digest instead of per-item pings."""
    # Validate the product exists if a catalog id was supplied.
    if payload.product_id is not None:
        product = db.query(Product).filter(Product.id == payload.product_id).first()
        if not product or not product.is_active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    req = Request(
        requester_id=user.id,
        product_id=payload.product_id,
        custom_product_name=payload.custom_product_name,
        quantity=payload.quantity,
        notes=payload.notes,
    )
    db.add(req)
    db.flush()  # populate req.id before history insert

    db.add(RequestHistory(
        request_id=req.id,
        status=RequestStatus.PENDING,
        changed_by=user.id,
    ))
    db.commit()
    db.refresh(req)
    return req


@router.get("", response_model=list[RequestOut])
def list_requests(
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List requests. Managers see only their own; buyers see everything."""
    q = db.query(Request)
    if user.role == UserRole.MANAGER:
        q = q.filter(Request.requester_id == user.id)
    if status_filter:
        q = q.filter(Request.status == status_filter)
    return q.order_by(Request.created_at.desc()).all()


@router.post("/clear-all", response_model=ClearAllResponse)
def clear_all_pending(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.BUYER)),
):
    """Buyer marks every pending request as done in one shot ('Got everything' button)."""
    pending = db.query(Request).filter(Request.status == RequestStatus.PENDING).all()

    for req in pending:
        req.status = RequestStatus.DONE
        db.add(RequestHistory(
            request_id=req.id,
            status=RequestStatus.DONE,
            changed_by=user.id,
        ))

    db.commit()

    cleared_ids = [req.id for req in pending]
    for rid in cleared_ids:
        background.add_task(notifications.notify_requester_status_change, rid)

    return {"cleared_count": len(cleared_ids), "request_ids": cleared_ids}


@router.post("/send-digest", response_model=DigestResponse)
def send_digest(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.BUYER)),
):
    """Manually trigger the daily digest SMS to all buyers."""
    count = notifications.send_daily_digest(db)
    return {"items_in_digest": count}


@router.post("/archive-stale", response_model=ArchiveStaleResponse)
def archive_stale(
    hours: int = Query(default=48, ge=1, le=720),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.BUYER)),
):
    """Mark all pending requests older than `hours` as DONE (system auto-archive)."""
    count = archive_stale_pending_requests(db, max_age_hours=hours)
    return {"archived_count": count}


@router.get("/{request_id}", response_model=RequestOut)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    # Managers can only see their own requests.
    if user.role == UserRole.MANAGER and req.requester_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request")
    return req


@router.patch("/{request_id}/status", response_model=RequestOut)
def update_status(
    request_id: int,
    payload: RequestStatusUpdate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.BUYER)),
):
    """Buyer transitions a request through its lifecycle."""
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    if payload.status not in VALID_TRANSITIONS[req.status]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot transition from {req.status.value} to {payload.status.value}",
        )

    req.status = payload.status
    db.add(RequestHistory(
        request_id=req.id,
        status=payload.status,
        changed_by=user.id,
    ))
    db.commit()
    db.refresh(req)

    background.add_task(notifications.notify_requester_status_change, req.id)
    return req


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hard-delete a request. Managers can only delete their own; buyers can delete any."""
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    if user.role == UserRole.MANAGER and req.requester_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request")

    db.delete(req)
    db.commit()

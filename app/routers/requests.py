"""Restock request routes — the heart of the app."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.product import Product
from app.models.request import Request, RequestHistory, RequestStatus
from app.models.user import User
from app.schemas.request import ArchiveStaleResponse, ClearAllResponse, DigestResponse, MarkDoneRequest, MarkDoneResponse, RequestCreate, RequestOut, RequestStatusUpdate
from app.services import notifications
from app.services.archive import archive_stale_pending_requests


router = APIRouter(prefix="/requests", tags=["requests"])


VALID_TRANSITIONS = {
    RequestStatus.PENDING: {RequestStatus.DONE},
    RequestStatus.DONE: set(),
}


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
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
    db.flush()

    db.add(RequestHistory(
        request_id=req.id,
        status=RequestStatus.PENDING,
        changed_by=user.id,
    ))
    db.commit()
    return (
        db.query(Request)
        .options(joinedload(Request.product))
        .filter(Request.id == req.id)
        .first()
    )


@router.get("", response_model=list[RequestOut])
def list_requests(
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Each user sees only their own requests."""
    q = (
        db.query(Request)
        .options(joinedload(Request.product))
        .filter(Request.requester_id == user.id)
    )
    if status_filter:
        q = q.filter(Request.status == status_filter)
    return q.order_by(Request.created_at.desc()).all()


@router.post("/clear-all", response_model=ClearAllResponse)
def clear_all_pending(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark every pending request as done in one shot."""
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
    return {"cleared_count": len(cleared_ids), "request_ids": cleared_ids}


@router.post("/send-digest", response_model=DigestResponse)
def send_digest(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Manually trigger the daily digest SMS."""
    count = notifications.send_daily_digest(db)
    return {"items_in_digest": count}


@router.post("/archive-stale", response_model=ArchiveStaleResponse)
def archive_stale(
    hours: int = Query(default=48, ge=1, le=720),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Mark all pending requests older than `hours` as DONE."""
    count = archive_stale_pending_requests(db, max_age_hours=hours)
    return {"archived_count": count}


@router.get("/{request_id}", response_model=RequestOut)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    req = (
        db.query(Request)
        .options(joinedload(Request.product))
        .filter(Request.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    return req


@router.post("/mark-done", response_model=MarkDoneResponse)
def mark_done(
    payload: MarkDoneRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a specific list of requests as done. Missing or already-done IDs are silently skipped."""
    marked_ids = []
    for rid in payload.request_ids:
        req = db.query(Request).filter(Request.id == rid).first()
        if req is None or req.status != RequestStatus.PENDING:
            continue
        req.status = RequestStatus.DONE
        db.add(RequestHistory(
            request_id=req.id,
            status=RequestStatus.DONE,
            changed_by=user.id,
        ))
        marked_ids.append(rid)
    db.commit()
    return {"marked_count": len(marked_ids), "request_ids": marked_ids}


@router.patch("/{request_id}/status", response_model=RequestOut)
def update_status(
    request_id: int,
    payload: RequestStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
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
    return (
        db.query(Request)
        .options(joinedload(Request.product))
        .filter(Request.id == request_id)
        .first()
    )


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hard-delete a request. Users can only delete their own."""
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    if req.requester_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request")

    db.delete(req)
    db.commit()

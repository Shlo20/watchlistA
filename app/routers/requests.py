"""Restock request routes — the heart of the app."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.product import Product
from app.models.request import Request, RequestHistory, RequestStatus, Urgency
from app.models.user import User, UserRole
from app.schemas.request import RequestCreate, RequestOut, RequestStatusUpdate
from app.services import notifications


router = APIRouter(prefix="/requests", tags=["requests"])


# Allowed status transitions. Anything not in this map is rejected.
VALID_TRANSITIONS = {
    RequestStatus.PENDING: {RequestStatus.ORDERED, RequestStatus.CANCELLED},
    RequestStatus.ORDERED: {RequestStatus.FULFILLED, RequestStatus.CANCELLED},
    RequestStatus.FULFILLED: set(),
    RequestStatus.CANCELLED: set(),
}


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RequestCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.MANAGER)),
):
    """Manager creates a restock request. Buyers get an SMS."""
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
        urgency=payload.urgency,
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

    # Notify all buyers in the background so the API response is fast.
    background.add_task(notifications.notify_buyers_new_request, req.id)
    return req


@router.get("", response_model=list[RequestOut])
def list_requests(
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
    urgency: Urgency | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List requests. Managers see only their own; buyers see everything."""
    q = db.query(Request)
    if user.role == UserRole.MANAGER:
        q = q.filter(Request.requester_id == user.id)
    if status_filter:
        q = q.filter(Request.status == status_filter)
    if urgency:
        q = q.filter(Request.urgency == urgency)
    return q.order_by(Request.created_at.desc()).all()


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
def cancel_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Soft-cancel a request. Managers can cancel their own pending ones; buyers can cancel any."""
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    if user.role == UserRole.MANAGER:
        if req.requester_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request")
        if req.status != RequestStatus.PENDING:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Managers can only cancel pending requests",
            )

    if req.status in (RequestStatus.FULFILLED, RequestStatus.CANCELLED):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Already in terminal state: {req.status.value}",
        )

    req.status = RequestStatus.CANCELLED
    db.add(RequestHistory(
        request_id=req.id,
        status=RequestStatus.CANCELLED,
        changed_by=user.id,
    ))
    db.commit()

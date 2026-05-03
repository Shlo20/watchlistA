"""Restock request model — the core of the app."""
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    ORDERED = "ordered"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class Urgency(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    URGENT = "urgent"


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Either picks from catalog OR free-types a custom name. Exactly one must be set.
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    custom_product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    urgency: Mapped[Urgency] = mapped_column(Enum(Urgency), default=Urgency.NORMAL, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    requester = relationship("User", back_populates="requests", foreign_keys=[requester_id])
    product = relationship("Product")
    history = relationship("RequestHistory", back_populates="request", cascade="all, delete-orphan")


class RequestHistory(Base):
    """Audit trail of every status change on a request."""
    __tablename__ = "request_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), nullable=False)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    request = relationship("Request", back_populates="history")

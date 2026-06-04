"""Send and SendItemState: delivery of a List to a recipient."""
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Send(Base):
    __tablename__ = "sends"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(
        ForeignKey("lists.id"), nullable=False, index=True
    )
    sender_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    recipient_phone: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # E.164, always set
    recipient_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    item_states = relationship(
        "SendItemState",
        back_populates="send",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SendItemState(Base):
    """Recipient's check-off state per item per send — keeps each recipient's progress independent."""

    __tablename__ = "send_item_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    send_id: Mapped[int] = mapped_column(
        ForeignKey("sends.id", ondelete="CASCADE"), nullable=False, index=True
    )
    list_item_id: Mapped[int] = mapped_column(
        ForeignKey("list_items.id"), nullable=False
    )
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    send = relationship("Send", back_populates="item_states")

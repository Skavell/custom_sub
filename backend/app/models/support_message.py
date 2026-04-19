from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"))
    author_type: Mapped[str] = mapped_column(String(10))  # user | admin
    text: Mapped[str] = mapped_column(Text)
    is_read_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped["SupportTicket"] = relationship("SupportTicket", back_populates="messages")  # noqa: F821

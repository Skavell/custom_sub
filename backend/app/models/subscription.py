import uuid
import enum
from datetime import datetime
from sqlalchemy import DateTime, Enum, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
from app.models.base import Base


class SubscriptionType(str, enum.Enum):
    trial = "trial"
    paid = "paid"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    disabled = "disabled"


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[SubscriptionType] = mapped_column(Enum(SubscriptionType))
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    traffic_limit_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="subscription")

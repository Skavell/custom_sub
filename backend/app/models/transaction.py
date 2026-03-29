import uuid
import enum
from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class TransactionType(str, enum.Enum):
    trial_activation = "trial_activation"
    payment = "payment"
    promo_bonus = "promo_bonus"
    manual = "manual"


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    promo_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("promo_codes.id"), nullable=True)
    amount_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_added: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="transactions")
    plan: Mapped["Plan | None"] = relationship()
    promo_code: Mapped["PromoCode | None"] = relationship()

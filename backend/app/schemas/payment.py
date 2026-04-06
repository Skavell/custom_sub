from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class CreatePaymentRequest(BaseModel):
    plan_id: uuid.UUID
    promo_code: str | None = None  # discount_percent only; bonus_days handled in Plan 4
    provider: str = "cryptobot"


class PaymentResponse(BaseModel):
    payment_url: str
    transaction_id: str
    amount_rub: int
    amount_usdt: str       # e.g. "2.41"
    is_existing: bool


class TransactionHistoryItem(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    amount_rub: int | None
    plan_name: str | None
    days_added: int | None
    created_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class CryptoBotWebhookPayload(BaseModel):
    """CryptoBot sends update_type='invoice_paid' with nested invoice in 'payload' field."""
    update_type: str
    update_id: int

    class Invoice(BaseModel):
        invoice_id: int
        status: str          # "paid" | "active" | "expired"
        asset: str
        amount: str
        payload: str         # our order_id = transaction.id (UUID string)
        model_config = {"extra": "allow"}

    payload: Invoice
    model_config = {"extra": "allow"}


class PaymentProviderInfo(BaseModel):
    name: str
    label: str
    is_active: bool

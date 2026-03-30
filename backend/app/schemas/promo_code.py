# backend/app/schemas/promo_code.py
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class ValidatePromoResponse(BaseModel):
    code: str
    type: str           # "discount_percent" | "bonus_days"
    value: int          # percent value or days count
    already_used: bool


class ApplyPromoRequest(BaseModel):
    code: str


class ApplyPromoResponse(BaseModel):
    days_added: int
    new_expires_at: datetime

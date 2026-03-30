# backend/app/schemas/admin.py
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class ProviderInfo(BaseModel):
    provider: str
    provider_user_id: str
    provider_username: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class SubscriptionAdminInfo(BaseModel):
    type: str
    status: str
    started_at: datetime
    expires_at: datetime
    traffic_limit_gb: int | None
    synced_at: datetime | None
    model_config = {"from_attributes": True}


class TransactionAdminItem(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    amount_rub: int | None
    days_added: int | None
    description: str | None
    created_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class UserAdminListItem(BaseModel):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    is_admin: bool
    remnawave_uuid: uuid.UUID | None
    has_made_payment: bool
    subscription_conflict: bool
    created_at: datetime
    last_seen_at: datetime
    subscription_status: str | None
    subscription_type: str | None
    subscription_expires_at: datetime | None
    providers: list[str]


class UserAdminDetail(BaseModel):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    is_admin: bool
    remnawave_uuid: uuid.UUID | None
    has_made_payment: bool
    subscription_conflict: bool
    created_at: datetime
    last_seen_at: datetime
    subscription: SubscriptionAdminInfo | None
    providers: list[ProviderInfo]
    recent_transactions: list[TransactionAdminItem]


class ConflictResolveRequest(BaseModel):
    remnawave_uuid: str  # UUID string of the Remnawave user to keep


class SyncStatusResponse(BaseModel):
    status: str   # "running" | "completed" | "failed" | "timed_out"
    total: int
    done: int
    errors: int

# backend/app/schemas/admin.py
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class ProviderInfo(BaseModel):
    provider: str
    provider_user_id: str
    provider_username: str | None
    email_verified: bool | None = None
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
    is_banned: bool = False
    remnawave_uuid: uuid.UUID | None
    has_made_payment: bool
    subscription_conflict: bool
    created_at: datetime
    last_seen_at: datetime
    subscription_status: str | None
    subscription_type: str | None
    subscription_expires_at: datetime | None
    providers: list[str]
    email: str | None = None
    email_verified: bool | None = None


class UserAdminDetail(BaseModel):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    is_admin: bool
    is_banned: bool = False
    remnawave_uuid: uuid.UUID | None
    has_made_payment: bool
    subscription_conflict: bool
    created_at: datetime
    last_seen_at: datetime
    subscription: SubscriptionAdminInfo | None
    providers: list[ProviderInfo]
    recent_transactions: list[TransactionAdminItem]
    email: str | None = None
    email_verified: bool | None = None


class ConflictResolveRequest(BaseModel):
    remnawave_uuid: str  # UUID string of the Remnawave user to keep


class SyncStatusResponse(BaseModel):
    status: str   # "running" | "completed" | "failed" | "timed_out"
    total: int
    done: int
    errors: int


# --- Plans ---

class PlanAdminItem(BaseModel):
    id: uuid.UUID
    name: str
    label: str
    duration_days: int
    price_rub: int
    new_user_price_rub: int | None
    is_active: bool
    sort_order: int
    model_config = {"from_attributes": True}


class PlanUpdateRequest(BaseModel):
    label: str | None = None
    duration_days: int | None = None
    price_rub: int | None = None
    new_user_price_rub: int | None = None
    is_active: bool | None = None


class PlanCreateRequest(BaseModel):
    name: str                          # unique system key e.g. "2_months"
    label: str                         # display name e.g. "2 месяца"
    duration_days: int
    price_rub: int
    new_user_price_rub: int | None = None
    is_active: bool = True
    sort_order: int = 0


# --- Promo Codes ---

class PromoCodeAdminItem(BaseModel):
    id: uuid.UUID
    code: str
    type: str
    value: int
    max_uses: int | None
    used_count: int
    valid_until: datetime | None
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class PromoCodeCreateRequest(BaseModel):
    code: str
    type: str  # "discount_percent" | "bonus_days"
    value: int
    max_uses: int | None = None
    valid_until: datetime | None = None
    is_active: bool = True


# --- Articles ---

class ArticleAdminListItem(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    preview_image_url: str | None
    is_published: bool
    sort_order: int
    created_at: datetime
    model_config = {"from_attributes": True}


class ArticleAdminDetail(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    content: str
    preview_image_url: str | None
    is_published: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ArticleCreateRequest(BaseModel):
    slug: str
    title: str
    content: str
    preview_image_url: str | None = None
    sort_order: int = 0
    is_published: bool = False


class ArticleUpdateRequest(BaseModel):
    slug: str | None = None
    title: str | None = None
    content: str | None = None
    preview_image_url: str | None = None
    sort_order: int | None = None


# --- Settings ---

class SettingAdminItem(BaseModel):
    key: str
    value: str  # "***" if sensitive
    is_sensitive: bool
    updated_at: datetime


class SettingUpsertRequest(BaseModel):
    value: str
    is_sensitive: bool = False


# --- Support Messages ---

class SupportMessageAdminItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    message: str
    created_at: datetime
    model_config = {"from_attributes": True}

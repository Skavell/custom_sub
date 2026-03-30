from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class ArticleListItem(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    preview_image_url: str | None
    sort_order: int
    created_at: datetime
    model_config = {"from_attributes": True}


class ArticleDetail(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    content: str
    preview_image_url: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

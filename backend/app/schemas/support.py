import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


# --- Запросы ---

class CreateTicketRequest(BaseModel):
    subject: str
    text: str

    @field_validator("subject")
    @classmethod
    def subject_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Тема не может быть пустой")
        if len(v) > 255:
            raise ValueError("Тема слишком длинная (максимум 255 символов)")
        return v

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Сообщение не может быть пустым")
        if len(v) > 2000:
            raise ValueError("Сообщение слишком длинное (максимум 2000 символов)")
        return v


class AddMessageRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Сообщение не может быть пустым")
        if len(v) > 2000:
            raise ValueError("Сообщение слишком длинное (максимум 2000 символов)")
        return v


# --- Ответы ---

class SupportMessageOut(BaseModel):
    id: uuid.UUID
    author_type: str
    text: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SupportTicketOut(BaseModel):
    id: uuid.UUID
    number: int
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime
    unread_count: int = 0
    model_config = {"from_attributes": True}


class SupportTicketDetailOut(SupportTicketOut):
    messages: list[SupportMessageOut] = []


# --- Для админки ---

class SupportTicketAdminOut(SupportTicketOut):
    user_id: uuid.UUID
    user_display_name: str
    user_email: str | None
    message_count: int = 0

from pydantic import BaseModel, field_validator


class SupportMessageRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Сообщение не может быть пустым")
        if len(v) > 2000:
            raise ValueError("Сообщение слишком длинное (максимум 2000 символов)")
        return v

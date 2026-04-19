import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.support_ticket import SupportTicket
from app.models.support_message import SupportMessage


def _make_user(**kwargs):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.display_name = "Тест"
    u.has_made_payment = False
    for k, v in kwargs.items():
        setattr(u, k, v)
    return u


def _override_user(user):
    async def _dep():
        return user
    return _dep


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


@pytest.mark.asyncio
async def test_create_ticket_returns_201():
    """POST /api/support/tickets создаёт обращение"""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)

    created_ticket = MagicMock(spec=SupportTicket)
    created_ticket.id = uuid.uuid4()
    created_ticket.number = 1
    created_ticket.subject = "Тест тема"
    created_ticket.status = "open"
    from datetime import datetime, timezone
    created_ticket.created_at = datetime.now(timezone.utc)
    created_ticket.updated_at = datetime.now(timezone.utc)

    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.commit = AsyncMock()

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)

    try:
        with patch("app.routers.support.send_admin_support_notification"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/support/tickets",
                    json={"subject": "Тест тема", "text": "Текст сообщения"},
                )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_ticket_empty_subject_returns_422():
    """POST /api/support/tickets с пустой темой возвращает 422"""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/support/tickets",
                json={"subject": "   ", "text": "Текст"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_ticket_empty_text_returns_422():
    """POST /api/support/tickets с пустым сообщением возвращает 422"""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/support/tickets",
                json={"subject": "Тема", "text": ""},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422

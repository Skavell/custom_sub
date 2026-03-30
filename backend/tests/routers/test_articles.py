# backend/tests/routers/test_articles.py
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.models.article import Article


NOW = datetime.now(tz=timezone.utc)


def _make_article(slug="test-slug", title="Тест", is_published=True):
    a = MagicMock(spec=Article)
    a.id = uuid.uuid4()
    a.slug = slug
    a.title = title
    a.content = "# Заголовок\n\nТекст статьи."
    a.preview_image_url = None
    a.is_published = is_published
    a.sort_order = 0
    a.created_at = NOW
    a.updated_at = NOW
    return a


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


@pytest.mark.asyncio
async def test_articles_list_returns_published():
    article = _make_article()
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[article])))
    ))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/articles")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["slug"] == "test-slug"


@pytest.mark.asyncio
async def test_articles_list_empty():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    ))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/articles")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_articles_detail_found():
    article = _make_article(slug="how-to-install")
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=article)
    ))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/articles/how-to-install")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["slug"] == "how-to-install"
    assert "content" in resp.json()


@pytest.mark.asyncio
async def test_articles_detail_not_found():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=None)
    ))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/articles/nonexistent")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404

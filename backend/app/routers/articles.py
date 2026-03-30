# backend/app/routers/articles.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article import Article
from app.schemas.article import ArticleDetail, ArticleListItem

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=list[ArticleListItem])
async def list_articles(
    db: AsyncSession = Depends(get_db),
) -> list[ArticleListItem]:
    result = await db.execute(
        select(Article)
        .where(Article.is_published == True)
        .order_by(Article.sort_order.asc())
    )
    articles = result.scalars().all()
    return [ArticleListItem.model_validate(a) for a in articles]


@router.get("/{slug}", response_model=ArticleDetail)
async def get_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> ArticleDetail:
    result = await db.execute(
        select(Article).where(Article.slug == slug, Article.is_published == True)
    )
    article = result.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена")
    return ArticleDetail.model_validate(article)

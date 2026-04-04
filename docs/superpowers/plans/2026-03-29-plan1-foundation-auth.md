# Skavellion — Plan 1: Foundation + Authentication

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a fully working Docker Compose stack with PostgreSQL, Redis, Nginx, FastAPI backend, and complete authentication (email, Telegram OAuth, Google OAuth, VK OAuth) with JWT sessions in httpOnly cookies.

**Architecture:** FastAPI backend with SQLAlchemy async ORM and Alembic migrations. All auth providers unified through a single `auth_providers` table. JWT access (15min) + refresh (30d) tokens in httpOnly cookies with Redis-backed rotation and blacklisting.

**Tech Stack:** Python 3.12 + uv, FastAPI, SQLAlchemy 2.x async, Alembic, PostgreSQL 16, Redis 7, Docker Compose, Nginx. Tests: pytest + pytest-asyncio + httpx.

**Spec:** `docs/superpowers/specs/2026-03-29-skavellion-vpn-site-design.md`

**This plan covers:** Tasks 1–10 (Foundation, DB, Auth). Plans 2 and 3 cover backend business logic and frontend respectively.

---

## File Map

```
custom_sub_pages/
├── .gitignore
├── .env.example
├── docker-compose.yml
├── docker-compose.dev.yml
├── README.md
│
├── nginx/
│   └── nginx.conf
│
└── backend/
    ├── pyproject.toml          # uv project, dependencies, pytest config
    ├── uv.lock                 # committed
    ├── .python-version         # "3.12"
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py
    │   └── versions/           # migration files go here
    └── app/
        ├── __init__.py
        ├── main.py             # FastAPI app, lifespan, middleware, routers
        ├── config.py           # Pydantic Settings from env vars
        ├── database.py         # async engine, session factory, get_db dep
        ├── redis_client.py     # Redis connection, get_redis dep
        ├── deps.py             # get_current_user, require_admin dependencies
        │
        ├── models/
        │   ├── __init__.py     # re-exports all models for Alembic
        │   ├── base.py         # declarative Base
        │   ├── user.py         # User model
        │   ├── auth_provider.py # AuthProvider model
        │   ├── subscription.py # Subscription model (empty at this stage)
        │   ├── plan.py         # Plan model (empty at this stage)
        │   ├── transaction.py  # Transaction model (empty at this stage)
        │   ├── promo_code.py   # PromoCode + PromoCodeUsage (empty at this stage)
        │   ├── article.py      # Article model (empty at this stage)
        │   └── setting.py      # Setting model
        │
        ├── schemas/
        │   ├── __init__.py
        │   └── auth.py         # Request/response Pydantic schemas for auth
        │
        ├── routers/
        │   ├── __init__.py
        │   ├── auth.py         # POST /api/auth/register, login, logout, refresh, oauth/*
        │   └── users.py        # GET /api/users/me, POST /api/users/me/providers, DELETE provider
        │
        └── services/
            ├── __init__.py
            ├── auth/
            │   ├── __init__.py
            │   ├── jwt_service.py      # create_access_token, create_refresh_token, verify_token
            │   ├── password_service.py # hash_password, verify_password (bcrypt)
            │   └── oauth/
            │       ├── __init__.py
            │       ├── telegram.py     # verify_telegram_widget_data(data) -> TelegramUser
            │       ├── google.py       # exchange_code(code, redirect_uri) -> GoogleUser
            │       └── vk.py           # exchange_code(code, redirect_uri) -> VKUser
            └── user_service.py         # get_or_create_user_from_provider, link_provider, etc.
```

---

## Task 1: Project Scaffold + Git

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Initialize git repo**
```bash
cd E:/Projects/vpn/custom_sub_pages
git init
git checkout -b main
```

- [ ] **Step 2: Create .gitignore**
```
# Python
.venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
*.egg-info/
dist/
build/
.coverage
htmlcov/

# Node
node_modules/
frontend/dist/

# Env
.env
*.env.local

# Docker
postgres_data/
redis_data/

# IDE
.idea/
.vscode/
*.swp

# Project specific
.superpowers/
```

- [ ] **Step 3: Create .env.example**
```bash
# Copy this file to .env and fill in values
DATABASE_URL=postgresql+asyncpg://skavellion:password@localhost:5432/skavellion
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=change-me-to-64-random-bytes
SETTINGS_ENCRYPTION_KEY=change-me-to-32-random-bytes
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
VK_CLIENT_ID=
VK_CLIENT_SECRET=
ENVIRONMENT=development
FRONTEND_URL=http://localhost:5173
```

- [ ] **Step 4: Initial commit**
```bash
git add .gitignore .env.example
git commit -m "chore: initial project scaffold"
```

---

## Task 2: Docker Compose Infrastructure

**Files:**
- Create: `docker-compose.yml`
- Create: `docker-compose.dev.yml`
- Create: `nginx/nginx.conf`

- [ ] **Step 1: Create docker-compose.yml**
```yaml
services:
  nginx:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./frontend/dist:/usr/share/nginx/html:ro
    depends_on:
      - backend
    networks:
      - app

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
      - SETTINGS_ENCRYPTION_KEY=${SETTINGS_ENCRYPTION_KEY}
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
      - VK_CLIENT_ID=${VK_CLIENT_ID}
      - VK_CLIENT_SECRET=${VK_CLIENT_SECRET}
      - ENVIRONMENT=production
      - FRONTEND_URL=${FRONTEND_URL:-https://my.example.com}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - app

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: skavellion
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-password}
      POSTGRES_DB: skavellion
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U skavellion"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - app

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - app

volumes:
  postgres_data:
  redis_data:

networks:
  app:
    driver: bridge
```

- [ ] **Step 2: Create docker-compose.dev.yml** (overrides for local dev — exposes ports)
```yaml
services:
  postgres:
    ports:
      - "5432:5432"

  redis:
    ports:
      - "6379:6379"

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql+asyncpg://skavellion:password@postgres:5432/skavellion
      - REDIS_URL=redis://redis:6379/0
```

- [ ] **Step 3: Create nginx/nginx.conf**
```nginx
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    upstream backend {
        server backend:8000;
    }

    server {
        listen 80;
        server_name _;

        # API proxy
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Frontend SPA
        location / {
            root /usr/share/nginx/html;
            try_files $uri $uri/ /index.html;
            add_header X-Content-Type-Options nosniff;
            add_header X-Frame-Options DENY;
            add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://telegram.org; connect-src 'self'; style-src 'self' 'unsafe-inline'";
        }
    }
}
```

- [ ] **Step 4: Commit**
```bash
git add docker-compose.yml docker-compose.dev.yml nginx/
git commit -m "feat: add docker-compose infrastructure and nginx config"
```

---

## Task 3: Backend Python Project Setup

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.python-version`
- Create: `backend/Dockerfile`
- Create: `backend/Dockerfile.dev`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`

- [ ] **Step 1: Initialize uv project**
```bash
cd backend
uv init --no-workspace --python 3.12
echo "3.12" > .python-version
```

- [ ] **Step 2: Add dependencies to pyproject.toml**

Replace the generated `pyproject.toml` with:
```toml
[project]
name = "skavellion-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "redis[hiredis]>=5.0.0",
    "pydantic-settings>=2.5.0",
    "pydantic[email]>=2.9.0",
    "bcrypt>=4.2.0",
    "python-jose[cryptography]>=3.3.0",
    "httpx>=0.27.0",
    "cryptography>=43.0.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-httpx>=0.30.0",
    "httpx>=0.27.0",
    "factory-boy>=3.3.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: Install dependencies**
```bash
uv sync
```

- [ ] **Step 4: Create app/config.py**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str
    settings_encryption_key: str
    google_client_id: str = ""
    google_client_secret: str = ""
    vk_client_id: str = ""
    vk_client_secret: str = ""
    environment: str = "development"
    frontend_url: str = "http://localhost:5173"

    # JWT
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
```

- [ ] **Step 5: Create app/main.py**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Skavellion API",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Create Dockerfile**
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Create Dockerfile.dev**
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 8: Create `__init__.py` files for all packages**
```bash
touch backend/app/services/__init__.py
touch backend/app/services/auth/__init__.py
touch backend/app/services/auth/oauth/__init__.py
touch backend/app/schemas/__init__.py
touch backend/app/routers/__init__.py
mkdir -p backend/tests/services backend/tests/routers
touch backend/tests/__init__.py backend/tests/services/__init__.py backend/tests/routers/__init__.py
```

- [ ] **Step 9: Commit**
```bash
cd ..
git add backend/
git commit -m "feat: backend python project setup with fastapi and uv"
```

---

## Task 4: Database — SQLAlchemy Models

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/redis_client.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/auth_provider.py`
- Create: `backend/app/models/subscription.py`
- Create: `backend/app/models/plan.py`
- Create: `backend/app/models/transaction.py`
- Create: `backend/app/models/promo_code.py`
- Create: `backend/app/models/article.py`
- Create: `backend/app/models/setting.py`
- Create: `backend/app/models/__init__.py`

- [ ] **Step 1: Create app/database.py**
```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 2: Create app/redis_client.py**
```python
from redis.asyncio import Redis
from app.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis
```

- [ ] **Step 3: Create app/models/base.py**
```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: Create app/models/user.py**
```python
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    remnawave_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    has_made_payment: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    auth_providers: Mapped[list["AuthProvider"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    subscription: Mapped["Subscription | None"] = relationship(back_populates="user", uselist=False)
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
```

- [ ] **Step 5: Create app/models/auth_provider.py**
```python
import uuid
import enum
from datetime import datetime
from sqlalchemy import DateTime, Enum, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
from app.models.base import Base


class ProviderType(str, enum.Enum):
    telegram = "telegram"
    google = "google"
    vk = "vk"
    email = "email"


class AuthProvider(Base):
    __tablename__ = "auth_providers"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[ProviderType] = mapped_column(Enum(ProviderType))
    provider_user_id: Mapped[str] = mapped_column(String(255))
    provider_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="auth_providers")
```

- [ ] **Step 6: Create app/models/subscription.py**
```python
import uuid
import enum
from datetime import datetime
from sqlalchemy import DateTime, Enum, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
from app.models.base import Base


class SubscriptionType(str, enum.Enum):
    trial = "trial"
    paid = "paid"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    disabled = "disabled"


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    type: Mapped[SubscriptionType] = mapped_column(Enum(SubscriptionType))
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    traffic_limit_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="subscription")
```

- [ ] **Step 7: Create app/models/plan.py**
```python
import uuid
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    label: Mapped[str] = mapped_column(String(100))
    duration_days: Mapped[int] = mapped_column(Integer)
    price_rub: Mapped[int] = mapped_column(Integer)
    new_user_price_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 8: Create app/models/transaction.py**
```python
import uuid
import enum
from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class TransactionType(str, enum.Enum):
    trial_activation = "trial_activation"
    payment = "payment"
    promo_bonus = "promo_bonus"
    manual = "manual"


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    promo_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("promo_codes.id"), nullable=True)
    amount_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_added: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="transactions")
```

- [ ] **Step 9: Create app/models/promo_code.py**
```python
import uuid
import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class PromoCodeType(str, enum.Enum):
    discount_percent = "discount_percent"
    bonus_days = "bonus_days"


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True)  # stored uppercase
    type: Mapped[PromoCodeType] = mapped_column(Enum(PromoCodeType))
    value: Mapped[int] = mapped_column(Integer)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PromoCodeUsage(Base):
    __tablename__ = "promo_code_usages"
    __table_args__ = (UniqueConstraint("promo_code_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    promo_code_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("promo_codes.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 10: Create app/models/article.py**
```python
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    preview_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 11: Create app/models/setting.py**
```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 12: Create app/models/__init__.py** (so Alembic can import all models)
```python
from app.models.base import Base
from app.models.user import User
from app.models.auth_provider import AuthProvider, ProviderType
from app.models.subscription import Subscription, SubscriptionType, SubscriptionStatus
from app.models.plan import Plan
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.promo_code import PromoCode, PromoCodeUsage, PromoCodeType
from app.models.article import Article
from app.models.setting import Setting

__all__ = [
    "Base", "User", "AuthProvider", "ProviderType",
    "Subscription", "SubscriptionType", "SubscriptionStatus",
    "Plan", "Transaction", "TransactionType", "TransactionStatus",
    "PromoCode", "PromoCodeUsage", "PromoCodeType",
    "Article", "Setting",
]
```

- [ ] **Step 13: Commit**
```bash
git add backend/app/
git commit -m "feat: add all sqlalchemy models"
```

---

## Task 5: Alembic Migrations

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/` (directory)

- [ ] **Step 1: Initialize Alembic**
```bash
cd backend
uv run alembic init alembic
```

- [ ] **Step 2: Update alembic/env.py** to use async engine and import models
```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from app.config import settings
from app.models import Base  # imports all models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Note: Uses asyncpg directly — no psycopg2 needed.

- [ ] **Step 3: Generate initial migration** (requires postgres running)
```bash
docker compose -f docker-compose.dev.yml up -d postgres
sleep 3
uv run alembic revision --autogenerate -m "initial schema"
```

- [ ] **Step 4: Run migration**
```bash
uv run alembic upgrade head
```
Expected: All tables created without errors.

- [ ] **Step 5: Commit**
```bash
git add alembic/ alembic.ini
git commit -m "feat: add alembic migrations for initial schema"
```

---

## Task 6: JWT + Password Services

**Files:**
- Create: `backend/app/services/auth/jwt_service.py`
- Create: `backend/app/services/auth/password_service.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/services/test_jwt_service.py`
- Create: `backend/tests/services/test_password_service.py`

- [ ] **Step 1: Write failing tests for JWT service**

Create `backend/tests/services/test_jwt_service.py`:
```python
import pytest
from datetime import timedelta
from app.services.auth.jwt_service import (
    create_access_token,
    create_refresh_token,
    verify_token,
    TokenType,
)


def test_access_token_roundtrip():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(user_id)
    payload = verify_token(token, TokenType.ACCESS)
    assert payload["sub"] == user_id


def test_refresh_token_roundtrip():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_refresh_token(user_id)
    payload = verify_token(token, TokenType.REFRESH)
    assert payload["sub"] == user_id


def test_access_token_rejected_as_refresh():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(user_id)
    with pytest.raises(ValueError, match="Invalid token type"):
        verify_token(token, TokenType.REFRESH)


def test_expired_token_raises():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(user_id, expires_delta=timedelta(seconds=-1))
    with pytest.raises(ValueError, match="expired"):
        verify_token(token, TokenType.ACCESS)
```

- [ ] **Step 2: Run tests — expect FAIL**
```bash
cd backend
uv run pytest tests/services/test_jwt_service.py -v
```
Expected: ImportError (module not yet created)

- [ ] **Step 3: Write JWT service**

Create `backend/app/services/auth/jwt_service.py`:
```python
import enum
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.config import settings


class TokenType(str, enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    return jwt.encode(
        {"sub": user_id, "type": TokenType.ACCESS, "exp": expire},
        settings.secret_key,
        algorithm="HS256",
    )


def create_refresh_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    return jwt.encode(
        {"sub": user_id, "type": TokenType.REFRESH, "exp": expire},
        settings.secret_key,
        algorithm="HS256",
    )


def verify_token(token: str, expected_type: TokenType) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError as e:
        if "expired" in str(e).lower():
            raise ValueError("Token expired")
        raise ValueError(f"Invalid token: {e}")

    if payload.get("type") != expected_type:
        raise ValueError(f"Invalid token type: expected {expected_type}")

    return payload
```

- [ ] **Step 4: Create tests/conftest.py**
```python
import pytest
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-testing-purposes-1234")
os.environ.setdefault("SETTINGS_ENCRYPTION_KEY", "test-encryption-key-32-bytes!!!")
```

- [ ] **Step 5: Run JWT tests — expect PASS**
```bash
uv run pytest tests/services/test_jwt_service.py -v
```
Expected: 4 PASSED

- [ ] **Step 6: Write failing tests for password service**

Create `backend/tests/services/test_password_service.py`:
```python
from app.services.auth.password_service import hash_password, verify_password


def test_hash_and_verify():
    password = "MySecurePassword123!"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_wrong_password_rejected():
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_hash_is_not_plaintext():
    password = "secret"
    hashed = hash_password(password)
    assert hashed != password
```

- [ ] **Step 7: Implement password service**

Create `backend/app/services/auth/password_service.py`:
```python
import bcrypt


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

- [ ] **Step 8: Run all service tests — expect PASS**
```bash
uv run pytest tests/services/ -v
```
Expected: 7 PASSED

- [ ] **Step 9: Commit**
```bash
git add backend/app/services/ backend/tests/
git commit -m "feat: add jwt and password services with tests"
```

---

## Task 7: Auth Middleware — get_current_user Dependency

**Files:**
- Create: `backend/app/deps.py`
- Create: `backend/tests/test_deps.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_deps.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.deps import get_current_user
from fastapi import Request


@pytest.mark.asyncio
async def test_get_current_user_no_cookie_raises():
    request = MagicMock(spec=Request)
    request.cookies = {}
    with pytest.raises(Exception):  # HTTPException 401
        await get_current_user(request=request, db=AsyncMock(), redis=AsyncMock())


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises():
    request = MagicMock(spec=Request)
    request.cookies = {"access_token": "not.a.valid.token"}
    with pytest.raises(Exception):
        await get_current_user(request=request, db=AsyncMock(), redis=AsyncMock())
```

- [ ] **Step 2: Run tests — expect FAIL**
```bash
uv run pytest tests/test_deps.py -v
```

- [ ] **Step 3: Implement deps.py**

Create `backend/app/deps.py`:
```python
import uuid
from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.redis_client import get_redis
from app.models.user import User
from app.services.auth.jwt_service import TokenType, verify_token


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = verify_token(token, TokenType.ACCESS)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Check blacklist
    if await redis.exists(f"blacklist:{token}"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return current_user
```

- [ ] **Step 4: Run tests — expect PASS**
```bash
uv run pytest tests/test_deps.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**
```bash
git add backend/app/deps.py backend/tests/test_deps.py
git commit -m "feat: add get_current_user and require_admin dependencies"
```

---

## Task 8: Email Authentication Endpoints

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/user_service.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/tests/routers/test_auth_email.py`

- [ ] **Step 1: Write failing tests for email auth**

Create `backend/tests/routers/test_auth_email.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_register_email_success(client):
    with patch("app.routers.auth.get_db"), patch("app.routers.auth.get_redis"):
        resp = await client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "display_name": "Test User"
        })
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_register_short_password_rejected(client):
    resp = await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "short",
        "display_name": "Test"
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email_rejected(client):
    resp = await client.post("/api/auth/register", json={
        "email": "not-an-email",
        "password": "SecurePass123!",
        "display_name": "Test"
    })
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests — expect FAIL**
```bash
uv run pytest tests/routers/test_auth_email.py -v
```

- [ ] **Step 3: Create app/schemas/auth.py**
```python
from pydantic import BaseModel, EmailStr, field_validator


class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    user_id: str
    display_name: str


class TelegramOAuthRequest(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class GoogleOAuthRequest(BaseModel):
    code: str
    redirect_uri: str


class VKOAuthRequest(BaseModel):
    code: str
    redirect_uri: str
    device_id: str
    state: str
```

- [ ] **Step 4: Create app/services/user_service.py**
```python
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.auth_provider import AuthProvider, ProviderType
from app.services.auth.password_service import hash_password, verify_password


async def get_user_by_provider(
    db: AsyncSession, provider: ProviderType, provider_user_id: str
) -> User | None:
    result = await db.execute(
        select(User)
        .join(AuthProvider)
        .where(
            AuthProvider.provider == provider,
            AuthProvider.provider_user_id == provider_user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_user_with_provider(
    db: AsyncSession,
    display_name: str,
    provider: ProviderType,
    provider_user_id: str,
    avatar_url: str | None = None,
    provider_username: str | None = None,
    password: str | None = None,
) -> User:
    user = User(
        display_name=display_name,
        avatar_url=avatar_url,
    )
    db.add(user)
    await db.flush()

    auth_provider = AuthProvider(
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_username=provider_username,
        password_hash=hash_password(password) if password else None,
    )
    db.add(auth_provider)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> tuple[User | None, AuthProvider | None]:
    result = await db.execute(
        select(User, AuthProvider)
        .join(AuthProvider)
        .where(
            AuthProvider.provider == ProviderType.email,
            AuthProvider.provider_user_id == email.lower(),
        )
    )
    row = result.first()
    if not row:
        return None, None
    return row[0], row[1]
```

- [ ] **Step 5: Create app/routers/auth.py** (email registration + login + logout + refresh)
```python
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis_client import get_redis
from app.schemas.auth import EmailRegisterRequest, EmailLoginRequest, TokenResponse
from app.services.auth.jwt_service import create_access_token, create_refresh_token, verify_token, TokenType
from app.services.auth.password_service import verify_password
from app.services.user_service import create_user_with_provider, get_user_by_email
from app.models.auth_provider import ProviderType
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_OPTS = {
    "httponly": True,
    "samesite": "strict",
    "secure": settings.is_production,
}


def _set_auth_cookies(response: Response, user_id: str) -> None:
    access = create_access_token(str(user_id))
    refresh = create_refresh_token(str(user_id))
    response.set_cookie("access_token", access, max_age=settings.access_token_expire_minutes * 60, **COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh, max_age=settings.refresh_token_expire_days * 86400, **COOKIE_OPTS)


@router.post("/register", response_model=TokenResponse)
async def register_email(
    data: EmailRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    existing, _ = await get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await create_user_with_provider(
        db,
        display_name=data.display_name,
        provider=ProviderType.email,
        provider_user_id=data.email.lower(),
        password=data.password,
    )
    _set_auth_cookies(response, str(user.id))
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)


@router.post("/login", response_model=TokenResponse)
async def login_email(
    data: EmailLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user, provider = await get_user_by_email(db, data.email)
    if not user or not provider or not provider.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(data.password, provider.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _set_auth_cookies(response, str(user.id))
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
):
    access_token = request.cookies.get("access_token")
    if access_token:
        await redis.setex(f"blacklist:{access_token}", settings.access_token_expire_minutes * 60, "1")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"ok": True}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    from sqlalchemy import select
    from app.models.user import User
    import uuid

    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = verify_token(token, TokenType.REFRESH)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Invalidate old refresh token (rotation)
    await redis.delete(f"refresh:{token[:32]}")

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    _set_auth_cookies(response, str(user.id))
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)
```

- [ ] **Step 6: Register router in main.py**

Add to `app/main.py`:
```python
from app.routers import auth, users
app.include_router(auth.router)
# app.include_router(users.router)  # added in Task 10
```

- [ ] **Step 7: Run all tests — expect PASS**
```bash
uv run pytest tests/ -v
```
Expected: All passing (email tests will pass with mocked DB)

- [ ] **Step 8: Commit**
```bash
git add backend/app/schemas/ backend/app/services/user_service.py backend/app/routers/auth.py
git commit -m "feat: add email registration and login endpoints"
```

---

## Task 9: OAuth Providers (Telegram, Google, VK)

**Files:**
- Create: `backend/app/services/auth/oauth/telegram.py`
- Create: `backend/app/services/auth/oauth/google.py`
- Create: `backend/app/services/auth/oauth/vk.py`
- Create: `backend/tests/services/test_oauth_telegram.py`
- Modify: `backend/app/routers/auth.py` (add OAuth endpoints)

- [ ] **Step 1: Write failing test for Telegram OAuth verification**

Create `backend/tests/services/test_oauth_telegram.py`:
```python
import hashlib
import hmac
import time
import pytest
from app.services.auth.oauth.telegram import verify_telegram_data


def make_valid_data(bot_token: str = "test:token") -> dict:
    data = {
        "id": "123456789",
        "first_name": "Ivan",
        "auth_date": str(int(time.time())),
    }
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hashlib.sha256(bot_token.encode()).digest()
    hash_val = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return {**data, "hash": hash_val}


def test_valid_telegram_data_passes():
    import os
    os.environ["TELEGRAM_BOT_TOKEN_FOR_TEST"] = "test:token"
    data = make_valid_data("test:token")
    result = verify_telegram_data(data, bot_token="test:token")
    assert result["id"] == "123456789"


def test_tampered_data_rejected():
    data = make_valid_data("test:token")
    data["first_name"] = "Hacker"
    with pytest.raises(ValueError, match="Invalid"):
        verify_telegram_data(data, bot_token="test:token")


def test_expired_auth_date_rejected():
    data = make_valid_data("test:token")
    data["auth_date"] = "1000000000"  # way in the past
    # recompute valid hash for this data
    check_string = "\n".join(f"{k}={v}" for k, v in sorted({k: v for k, v in data.items() if k != "hash"}.items()))
    import hashlib, hmac
    secret = hashlib.sha256("test:token".encode()).digest()
    data["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    with pytest.raises(ValueError, match="expired"):
        verify_telegram_data(data, bot_token="test:token")
```

- [ ] **Step 2: Run tests — expect FAIL**
```bash
uv run pytest tests/services/test_oauth_telegram.py -v
```

- [ ] **Step 3: Implement Telegram OAuth verification**

Create `backend/app/services/auth/oauth/telegram.py`:
```python
import hashlib
import hmac
import time
from dataclasses import dataclass


@dataclass
class TelegramUser:
    id: int
    first_name: str
    last_name: str | None
    username: str | None
    photo_url: str | None


def verify_telegram_data(data: dict, bot_token: str, max_age_seconds: int = 86400) -> dict:
    received_hash = data.get("hash", "")
    auth_date = int(data.get("auth_date", 0))

    if time.time() - auth_date > max_age_seconds:
        raise ValueError("Telegram auth data expired")

    check_data = {k: v for k, v in data.items() if k != "hash"}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(check_data.items()))
    secret = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Invalid Telegram hash")

    return data


def parse_telegram_user(data: dict) -> TelegramUser:
    return TelegramUser(
        id=int(data["id"]),
        first_name=data["first_name"],
        last_name=data.get("last_name"),
        username=data.get("username"),
        photo_url=data.get("photo_url"),
    )
```

- [ ] **Step 4: Run Telegram tests — expect PASS**
```bash
uv run pytest tests/services/test_oauth_telegram.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Implement Google OAuth service**

Create `backend/app/services/auth/oauth/google.py`:
```python
from dataclasses import dataclass
import httpx
from app.config import settings


@dataclass
class GoogleUser:
    id: str
    email: str
    name: str
    picture: str | None


async def exchange_google_code(code: str, redirect_uri: str) -> GoogleUser:
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_resp.raise_for_status()
        info = userinfo_resp.json()

    return GoogleUser(
        id=info["id"],
        email=info["email"],
        name=info.get("name", info["email"]),
        picture=info.get("picture"),
    )
```

- [ ] **Step 6: Implement VK OAuth service**

Create `backend/app/services/auth/oauth/vk.py`:
```python
from dataclasses import dataclass
import httpx
from app.config import settings


@dataclass
class VKUser:
    id: str
    first_name: str
    last_name: str
    avatar: str | None


async def exchange_vk_code(code: str, redirect_uri: str, device_id: str, state: str) -> VKUser:
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://id.vk.com/oauth2/auth",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.vk_client_id,
                "client_secret": settings.vk_client_secret,
                "redirect_uri": redirect_uri,
                "device_id": device_id,
                "state": state,
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

        info_resp = await client.post(
            "https://id.vk.com/oauth2/user_info",
            data={"access_token": token_data["access_token"], "client_id": settings.vk_client_id},
        )
        info_resp.raise_for_status()
        user = info_resp.json()["user"]

    return VKUser(
        id=str(user["user_id"]),
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name", ""),
        avatar=user.get("avatar"),
    )
```

- [ ] **Step 7: Add OAuth endpoints to auth.py router**

Append to `backend/app/routers/auth.py`:
```python
from app.services.auth.oauth.telegram import verify_telegram_data, parse_telegram_user
from app.services.auth.oauth.google import exchange_google_code
from app.services.auth.oauth.vk import exchange_vk_code
from app.services.user_service import get_user_by_provider
from app.schemas.auth import TelegramOAuthRequest, GoogleOAuthRequest, VKOAuthRequest


@router.post("/oauth/telegram", response_model=TokenResponse)
async def oauth_telegram(
    data: TelegramOAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    from app.services.setting_service import get_setting
    bot_token = await get_setting(db, "telegram_bot_token") or ""
    try:
        raw = data.model_dump()
        verify_telegram_data(raw, bot_token=bot_token)
        tg_user = parse_telegram_user(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = await get_user_by_provider(db, ProviderType.telegram, str(tg_user.id))
    if not user:
        display_name = tg_user.first_name
        if tg_user.last_name:
            display_name += f" {tg_user.last_name}"
        user = await create_user_with_provider(
            db,
            display_name=display_name,
            provider=ProviderType.telegram,
            provider_user_id=str(tg_user.id),
            avatar_url=tg_user.photo_url,
            provider_username=tg_user.username,
        )

    _set_auth_cookies(response, str(user.id))
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)


@router.post("/oauth/google", response_model=TokenResponse)
async def oauth_google(
    data: GoogleOAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        g_user = await exchange_google_code(data.code, data.redirect_uri)
    except Exception:
        raise HTTPException(status_code=400, detail="Google OAuth failed")

    user = await get_user_by_provider(db, ProviderType.google, g_user.id)
    if not user:
        user = await create_user_with_provider(
            db,
            display_name=g_user.name,
            provider=ProviderType.google,
            provider_user_id=g_user.id,
            avatar_url=g_user.picture,
        )

    _set_auth_cookies(response, str(user.id))
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)


@router.post("/oauth/vk", response_model=TokenResponse)
async def oauth_vk(
    data: VKOAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        vk_user = await exchange_vk_code(data.code, data.redirect_uri, data.device_id, data.state)
    except Exception:
        raise HTTPException(status_code=400, detail="VK OAuth failed")

    user = await get_user_by_provider(db, ProviderType.vk, vk_user.id)
    if not user:
        user = await create_user_with_provider(
            db,
            display_name=f"{vk_user.first_name} {vk_user.last_name}".strip(),
            provider=ProviderType.vk,
            provider_user_id=vk_user.id,
            avatar_url=vk_user.avatar,
        )

    _set_auth_cookies(response, str(user.id))
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)
```

Note: `setting_service.get_setting` is needed for the Telegram bot token — create a stub:

Create `backend/app/services/setting_service.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.setting import Setting


async def get_setting(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        return None
    return setting.value.get("value")
```

- [ ] **Step 8: Run all tests**
```bash
uv run pytest tests/ -v
```
Expected: All PASSED

- [ ] **Step 9: Commit**
```bash
git add backend/app/services/auth/oauth/ backend/app/services/setting_service.py backend/app/routers/auth.py
git commit -m "feat: add telegram, google, vk oauth services and endpoints"
```

---

## Task 10: User Profile + Provider Link/Unlink Endpoints

**Files:**
- Create: `backend/app/routers/users.py`
- Create: `backend/app/schemas/user.py`
- Create: `backend/tests/routers/test_users.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/routers/test_users.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
import uuid


@pytest.mark.asyncio
async def test_get_me_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_returns_user_data():
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.display_name = "Test User"
    mock_user.avatar_url = None
    mock_user.is_admin = False
    mock_user.subscription_conflict = False
    mock_user.auth_providers = []

    with patch("app.deps.get_current_user", return_value=mock_user):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/users/me", cookies={"access_token": "fake"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Test User"
```

- [ ] **Step 2: Run tests — expect FAIL**
```bash
uv run pytest tests/routers/test_users.py -v
```

- [ ] **Step 3: Create app/schemas/user.py**
```python
import uuid
from pydantic import BaseModel
from app.models.auth_provider import ProviderType


class AuthProviderInfo(BaseModel):
    provider: ProviderType
    provider_username: str | None

    model_config = {"from_attributes": True}


class UserMe(BaseModel):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    is_admin: bool
    subscription_conflict: bool
    auth_providers: list[AuthProviderInfo]

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create app/routers/users.py**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.auth_provider import ProviderType
from app.schemas.user import UserMe

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserMe)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.delete("/me/providers/{provider}")
async def unlink_provider(
    provider: ProviderType,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    providers = current_user.auth_providers
    if len(providers) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove last auth provider")

    target = next((p for p in providers if p.provider == provider), None)
    if not target:
        raise HTTPException(status_code=404, detail="Provider not linked")

    await db.delete(target)
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 5: Register users router in main.py**

Add to `app/main.py`:
```python
from app.routers import users
app.include_router(users.router)
```

- [ ] **Step 6: Run all tests**
```bash
uv run pytest tests/ -v
```
Expected: All PASSED

- [ ] **Step 7: Final commit for Plan 1**
```bash
git add backend/app/routers/users.py backend/app/schemas/user.py backend/tests/routers/test_users.py
git commit -m "feat: add user profile and provider management endpoints"
```

---

## Task 11: Smoke Test — Docker Compose Up

**Goal:** Verify the full stack starts and the health endpoint responds.

- [ ] **Step 1: Copy env file**
```bash
cp .env.example .env
# Fill in SECRET_KEY and SETTINGS_ENCRYPTION_KEY with random values:
# SECRET_KEY=$(openssl rand -hex 32)
# SETTINGS_ENCRYPTION_KEY=$(openssl rand -hex 16)
```

- [ ] **Step 2: Start dev stack**
```bash
docker compose -f docker-compose.dev.yml up -d
```

- [ ] **Step 3: Run migrations in container**
```bash
docker compose -f docker-compose.dev.yml exec backend uv run alembic upgrade head
```

- [ ] **Step 4: Hit health endpoint**
```bash
curl http://localhost:8000/api/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 5: Run full test suite**
```bash
cd backend && uv run pytest tests/ -v
```
Expected: All PASSED

- [ ] **Step 6: Final plan-1 tag commit**
```bash
git add -A
git commit -m "chore: plan 1 complete — foundation and auth"
git tag plan-1-complete
```

---

## What's Next

**Plan 2** covers all business logic:
- Remnawave integration service
- Trial activation endpoint
- Payment (Cryptomus) + webhook
- Promo code endpoints
- Manual sync (background task)
- Support message → Telegram
- Admin CRUD (users, plans, promo codes, articles, settings)

**Plan 3** covers:
- React + Vite + Tailwind + Shadcn setup
- All 7 user-facing pages
- Admin panel UI

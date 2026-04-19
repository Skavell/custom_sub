from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.telegram_bot import start_polling, stop_polling
from app.routers import auth
from app.routers import users
from app.routers import plans
from app.routers import subscriptions
from app.routers import payments
from app.routers import promo_codes
from app.routers import install
from app.routers import support
from app.routers import articles
from app.routers import admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Telegram bot polling if configured
    try:
        from app.services.setting_service import get_setting_decrypted
        async with AsyncSessionLocal() as db:
            token = await get_setting_decrypted(db, "telegram_bot_token")
            chat_id = await get_setting_decrypted(db, "telegram_support_chat_id")
            if token and chat_id:
                await start_polling(token, chat_id)
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).warning(f"Could not start Telegram polling: {e}")

    yield

    await stop_polling()


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


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(plans.router)
app.include_router(subscriptions.router)
app.include_router(payments.router)
app.include_router(promo_codes.router)
app.include_router(install.router)
app.include_router(support.router)
app.include_router(articles.router)
app.include_router(admin.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}

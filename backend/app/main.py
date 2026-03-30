from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth
from app.routers import users
from app.routers import plans
from app.routers import subscriptions
from app.routers import payments
from app.routers import promo_codes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO (Task 4-5): init DB engine and run startup checks here
    yield
    # TODO (Task 4-5): dispose DB engine on shutdown


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


@app.get("/api/health")
async def health():
    return {"status": "ok"}

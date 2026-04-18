import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.auth_provider import AuthProvider, ProviderType
from app.services.auth.password_service import hash_password


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
    phone_number: str | None = None,
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
        phone_number=phone_number,
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

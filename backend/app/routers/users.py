from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.auth_provider import AuthProvider, ProviderType
from app.schemas.user import UserProfileResponse, ProviderInfo
from app.schemas.auth import GoogleOAuthRequest, VKOAuthRequest, TelegramOAuthRequest, LinkEmailRequest
from app.services.auth.oauth.google import exchange_google_code
from app.services.auth.oauth.vk import exchange_vk_code
from app.services.auth.oauth.telegram import verify_telegram_data, parse_telegram_user
from app.services.auth.password_service import hash_password
from app.services.setting_service import get_setting

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    result = await db.execute(
        select(AuthProvider).where(AuthProvider.user_id == current_user.id)
    )
    providers = result.scalars().all()

    return UserProfileResponse(
        id=str(current_user.id),
        display_name=current_user.display_name,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        providers=[
            ProviderInfo(type=p.provider.value, username=p.provider_username)
            for p in providers
        ],
    )


@router.delete("/me/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    # Validate provider string against enum
    try:
        provider_type = ProviderType(provider)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid provider: {provider}. Must be one of: {[p.value for p in ProviderType]}",
        )

    # Cannot unlink email provider
    if provider_type == ProviderType.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlink email provider",
        )

    # Load all providers for user
    result = await db.execute(
        select(AuthProvider).where(AuthProvider.user_id == current_user.id)
    )
    all_providers = result.scalars().all()

    # Find the provider to delete — must exist before checking count,
    # so that a missing provider always yields 404 (not "last provider" 400).
    target = next((p for p in all_providers if p.provider == provider_type), None)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider} is not linked to this account",
        )

    # Guard after confirming target exists: email is blocked above, so reaching
    # here with len==1 means the sole non-email provider would be removed.
    if len(all_providers) == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last authentication provider",
        )

    await db.delete(target)
    await db.commit()


async def _check_provider_not_taken(
    db: AsyncSession,
    provider: ProviderType,
    provider_user_id: str,
) -> None:
    """Raise 409 if provider is already linked to any user."""
    result = await db.execute(
        select(AuthProvider).where(
            AuthProvider.provider == provider,
            AuthProvider.provider_user_id == provider_user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот аккаунт уже привязан",
        )


@router.post("/me/providers/google", status_code=200)
async def link_google(
    data: GoogleOAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        g_user = await exchange_google_code(data.code, data.redirect_uri)
    except Exception:
        raise HTTPException(status_code=400, detail="Google OAuth failed")
    await _check_provider_not_taken(db, ProviderType.google, g_user.id)
    db.add(AuthProvider(
        user_id=current_user.id,
        provider=ProviderType.google,
        provider_user_id=g_user.id,
    ))
    await db.commit()
    return {"ok": True}


@router.post("/me/providers/vk", status_code=200)
async def link_vk(
    data: VKOAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        vk_user = await exchange_vk_code(data.code, data.redirect_uri, data.device_id, data.state)
    except Exception:
        raise HTTPException(status_code=400, detail="VK OAuth failed")
    await _check_provider_not_taken(db, ProviderType.vk, vk_user.id)
    db.add(AuthProvider(
        user_id=current_user.id,
        provider=ProviderType.vk,
        provider_user_id=vk_user.id,
        provider_username=None,
    ))
    await db.commit()
    return {"ok": True}


@router.post("/me/providers/telegram", status_code=200)
async def link_telegram(
    data: TelegramOAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    bot_token = await get_setting(db, "telegram_bot_token")
    if not bot_token:
        raise HTTPException(status_code=503, detail="Telegram OAuth not configured")
    try:
        raw = data.model_dump(exclude_none=True)
        verify_telegram_data(raw, bot_token=bot_token)
        tg_user = parse_telegram_user(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _check_provider_not_taken(db, ProviderType.telegram, str(tg_user.id))
    db.add(AuthProvider(
        user_id=current_user.id,
        provider=ProviderType.telegram,
        provider_user_id=str(tg_user.id),
        provider_username=tg_user.username,
    ))
    await db.commit()
    return {"ok": True}


@router.post("/me/providers/email", status_code=200)
async def link_email(
    data: LinkEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(AuthProvider).where(
            AuthProvider.provider == ProviderType.email,
            AuthProvider.provider_user_id == data.email.lower(),
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email уже используется")
    db.add(AuthProvider(
        user_id=current_user.id,
        provider=ProviderType.email,
        provider_user_id=data.email.lower(),
        password_hash=hash_password(data.password),
    ))
    await db.commit()
    return {"ok": True}

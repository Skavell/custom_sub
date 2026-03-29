from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.auth_provider import AuthProvider, ProviderType
from app.schemas.user import UserProfileResponse, ProviderInfo

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

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.setting import Setting
from app.config import settings as app_settings


async def get_setting(db: AsyncSession, key: str) -> str | None:
    """Get a non-sensitive setting value. Returns raw string or None."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        return None
    return setting.value.get("value")


async def get_setting_decrypted(db: AsyncSession, key: str) -> str | None:
    """Get a setting value, decrypting if is_sensitive=True."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        return None
    if setting.is_sensitive:
        encrypted_blob = setting.value.get("encrypted")
        if not encrypted_blob:
            return None
        # Deferred to avoid circular import
        from app.services.encryption_service import decrypt_value
        return decrypt_value(app_settings.settings_encryption_key, encrypted_blob)
    return setting.value.get("value")


async def set_setting(
    db: AsyncSession, key: str, value: str, is_sensitive: bool = False
) -> None:
    """Create or update a setting. Encrypts the value if is_sensitive=True."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()

    if is_sensitive:
        # Deferred to avoid circular import
        from app.services.encryption_service import encrypt_value
        encoded = encrypt_value(app_settings.settings_encryption_key, value)
        jsonb_value = {"encrypted": encoded}
    else:
        jsonb_value = {"value": value}

    if setting:
        setting.value = jsonb_value
        setting.is_sensitive = is_sensitive
    else:
        setting = Setting(key=key, value=jsonb_value, is_sensitive=is_sensitive)
        db.add(setting)

    await db.commit()

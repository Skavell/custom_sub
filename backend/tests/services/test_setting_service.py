import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.setting import Setting
from app.services.setting_service import get_setting_decrypted, set_setting

ENCRYPTION_KEY = "test-key-for-encryption-32-chars!"


def _make_db_with_setting(setting) -> AsyncSession:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=setting)
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_get_setting_decrypted_sensitive(monkeypatch):
    from app.config import settings as app_settings
    monkeypatch.setattr(app_settings, "settings_encryption_key", ENCRYPTION_KEY)

    from app.services.encryption_service import encrypt_value
    encrypted_blob = encrypt_value(ENCRYPTION_KEY, "my_secret_token")

    setting = MagicMock(spec=Setting)
    setting.is_sensitive = True
    setting.value = {"encrypted": encrypted_blob}

    db = _make_db_with_setting(setting)
    result = await get_setting_decrypted(db, "remnawave_token")
    assert result == "my_secret_token"


@pytest.mark.asyncio
async def test_get_setting_decrypted_non_sensitive():
    setting = MagicMock(spec=Setting)
    setting.is_sensitive = False
    setting.value = {"value": "https://remnawave.example.com"}

    db = _make_db_with_setting(setting)
    result = await get_setting_decrypted(db, "remnawave_url")
    assert result == "https://remnawave.example.com"


@pytest.mark.asyncio
async def test_get_setting_decrypted_missing():
    db = _make_db_with_setting(None)
    result = await get_setting_decrypted(db, "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_set_setting_non_sensitive():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    await set_setting(db, "remnawave_url", "https://example.com", is_sensitive=False)
    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.key == "remnawave_url"
    assert added.value == {"value": "https://example.com"}
    assert added.is_sensitive is False
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_setting_sensitive_encrypts(monkeypatch):
    from app.config import settings as app_settings
    monkeypatch.setattr(app_settings, "settings_encryption_key", ENCRYPTION_KEY)

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    await set_setting(db, "remnawave_token", "secret", is_sensitive=True)
    added = db.add.call_args[0][0]
    assert added.is_sensitive is True
    assert "encrypted" in added.value
    assert added.value["encrypted"] != "secret"

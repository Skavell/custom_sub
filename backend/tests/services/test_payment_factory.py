import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from app.services.payment_providers.factory import get_active_provider, _is_provider_active


@pytest.mark.asyncio
async def test_is_provider_active_returns_true_when_enabled_and_token_set():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="true") as mock_get,
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="mytoken"),
    ):
        result = await _is_provider_active(db, "cryptobot")
    assert result is True


@pytest.mark.asyncio
async def test_is_provider_active_returns_false_when_disabled():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="false"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="mytoken"),
    ):
        result = await _is_provider_active(db, "cryptobot")
    assert result is False


@pytest.mark.asyncio
async def test_is_provider_active_returns_false_when_token_missing():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="true"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value=None),
    ):
        result = await _is_provider_active(db, "cryptobot")
    assert result is False


@pytest.mark.asyncio
async def test_is_provider_active_returns_false_when_setting_absent():
    """Absent setting treated as 'false' (strict == 'true' check)."""
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value=None),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="mytoken"),
    ):
        result = await _is_provider_active(db, "cryptobot")
    assert result is False


@pytest.mark.asyncio
async def test_get_active_provider_unknown_raises_400():
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_active_provider(db, "nonexistent")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_active_provider_disabled_raises_400():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="false"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="tok"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_active_provider(db, "cryptobot")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_active_provider_no_token_raises_503():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="true"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value=None),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_active_provider(db, "cryptobot")
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_active_provider_returns_cryptobot_provider():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", side_effect=lambda db, key: "true" if key == "cryptobot_enabled" else "83"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="mytoken"),
    ):
        provider = await get_active_provider(db, "cryptobot")
    assert provider.name == "cryptobot"

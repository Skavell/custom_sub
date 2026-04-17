import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


@pytest.mark.asyncio
async def test_send_verification_email_calls_resend():
    """Calls Resend API with correct payload."""
    from app.services.email_service import send_verification_email

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        await send_verification_email(
            api_key="re_test_key",
            from_address="noreply@test.com",
            from_name="Test VPN",
            to_email="user@gmail.com",
            verify_url="https://example.com/verify-email?token=abc123",
        )

    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[0][0] == "https://api.resend.com/emails"
    payload = call_kwargs[1]["json"]
    assert payload["to"] == ["user@gmail.com"]
    assert "abc123" in payload["html"]


@pytest.mark.asyncio
async def test_send_verification_email_raises_on_http_error():
    """Propagates HTTPStatusError on Resend API failure."""
    from app.services.email_service import send_verification_email

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await send_verification_email(
                api_key="re_bad_key",
                from_address="noreply@test.com",
                from_name="VPN",
                to_email="user@gmail.com",
                verify_url="https://example.com/verify-email?token=xyz",
            )


@pytest.mark.asyncio
async def test_send_reset_email_calls_resend():
    from app.services.email_service import send_reset_email

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        await send_reset_email(
            api_key="re_test",
            from_address="noreply@test.com",
            from_name="Test VPN",
            to_email="user@gmail.com",
            reset_url="https://example.com/reset-password?token=xyz123",
        )

    mock_client.post.assert_called_once()
    payload = mock_client.post.call_args[1]["json"]
    assert payload["to"] == ["user@gmail.com"]
    assert payload["subject"] == "Сброс пароля"
    assert "xyz123" in payload["html"]

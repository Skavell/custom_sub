import pytest
from pytest_httpx import HTTPXMock

from app.services.telegram_alert import send_admin_alert


@pytest.mark.asyncio
async def test_sends_message(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.telegram.org/botmy-token/sendMessage",
        json={"ok": True},
    )
    await send_admin_alert("my-token", "12345", "Test alert")
    request = httpx_mock.get_request()
    import json
    body = json.loads(request.content)
    assert body["chat_id"] == "12345"
    assert body["text"] == "Test alert"


@pytest.mark.asyncio
async def test_no_op_on_missing_token():
    # Should not raise, should not make any HTTP calls
    await send_admin_alert(None, "12345", "Test")


@pytest.mark.asyncio
async def test_no_op_on_missing_chat_id():
    await send_admin_alert("token", None, "Test")


@pytest.mark.asyncio
async def test_swallows_http_error(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.telegram.org/botmy-token/sendMessage",
        status_code=500,
    )
    # Should NOT raise even on server error
    await send_admin_alert("my-token", "12345", "Test")

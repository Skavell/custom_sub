import hashlib
import hmac
import json
import httpx
import pytest
from pytest_httpx import HTTPXMock

from app.services.payment_providers.cryptobot import CryptoBotProvider


TOKEN = "test-token-123"
RATE = 83.0


@pytest.mark.asyncio
async def test_create_invoice_returns_invoice_result(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://pay.crypt.bot/api/createInvoice",
        json={
            "ok": True,
            "result": {
                "invoice_id": 12345,
                "bot_invoice_url": "https://t.me/CryptoBot?start=IVtest",
                "status": "active",
                "asset": "USDT",
                "amount": "2.41",
            },
        },
        status_code=200,
    )
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    result = await provider.create_invoice(
        amount_rub=200,
        order_id="some-uuid",
        description="1 месяц",
    )
    assert result.payment_url == "https://t.me/CryptoBot?start=IVtest"
    assert result.external_id == "12345"


@pytest.mark.asyncio
async def test_create_invoice_sends_correct_amount(httpx_mock: HTTPXMock):
    """200 RUB / 83 RUB per USDT = 2.41 USDT."""
    httpx_mock.add_response(
        method="POST",
        url="https://pay.crypt.bot/api/createInvoice",
        json={"ok": True, "result": {"invoice_id": 1, "bot_invoice_url": "t.me/x", "status": "active", "asset": "USDT", "amount": "2.41"}},
    )
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    await provider.create_invoice(amount_rub=200, order_id="x", description="test")
    request = httpx_mock.get_request()
    body = json.loads(request.content)
    assert body["amount"] == "2.41"
    assert body["asset"] == "USDT"
    assert body["payload"] == "x"
    assert request.headers["Crypto-Pay-API-Token"] == TOKEN


@pytest.mark.asyncio
async def test_create_invoice_http_error_raises(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://pay.crypt.bot/api/createInvoice",
        status_code=500,
    )
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    with pytest.raises(httpx.HTTPStatusError):
        await provider.create_invoice(amount_rub=200, order_id="x", description="test")


def test_verify_webhook_valid():
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    raw_body = b'{"update_type":"invoice_paid"}'
    secret = hashlib.sha256(TOKEN.encode()).digest()
    sig = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    assert provider.verify_webhook(raw_body, {"crypto-pay-api-signature": sig}) is True


def test_verify_webhook_invalid_signature():
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    raw_body = b'{"update_type":"invoice_paid"}'
    assert provider.verify_webhook(raw_body, {"crypto-pay-api-signature": "deadbeef"}) is False


@pytest.mark.asyncio
async def test_create_invoice_api_error_raises(httpx_mock: HTTPXMock):
    """HTTP 200 with ok=false should raise, not silently fail."""
    httpx_mock.add_response(
        method="POST",
        url="https://pay.crypt.bot/api/createInvoice",
        json={"ok": False, "error": {"code": 401, "name": "UNAUTHORIZED"}},
        status_code=200,
    )
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    with pytest.raises(ValueError):
        await provider.create_invoice(amount_rub=200, order_id="x", description="test")

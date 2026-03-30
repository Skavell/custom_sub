import hashlib
import hmac
import json
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.plan import Plan


NOW = datetime.now(tz=timezone.utc)
TOKEN = "test-token-123"


def _make_sig(token: str, body: bytes) -> str:
    secret = hashlib.sha256(token.encode()).digest()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def _make_transaction(status=TransactionStatus.pending) -> Transaction:
    tx = MagicMock(spec=Transaction)
    tx.id = uuid.uuid4()
    tx.status = status
    tx.user_id = uuid.uuid4()
    tx.plan_id = uuid.uuid4()
    tx.promo_code_id = None
    tx.amount_rub = 200
    return tx


def _make_plan() -> Plan:
    p = MagicMock(spec=Plan)
    p.id = uuid.uuid4()
    p.label = "1 месяц"
    p.duration_days = 30
    return p


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _make_webhook_body(order_id: str, status: str = "paid") -> bytes:
    return json.dumps({
        "update_type": "invoice_paid",
        "update_id": 1,
        "request_date": "2026-03-30T12:00:00Z",
        "payload": {
            "invoice_id": 12345,
            "status": status,
            "asset": "USDT",
            "amount": "2.41",
            "payload": order_id,
        },
    }).encode()


@pytest.mark.asyncio
async def test_webhook_invalid_ip_returns_400():
    body = _make_webhook_body(str(uuid.uuid4()))
    db = AsyncMock(spec=AsyncSession)
    # IP list contains "1.2.3.4" — our request comes from testclient (127.0.0.1)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(
        return_value=MagicMock(is_sensitive=False, value={"value": '["1.2.3.4"]'})
    )
    db.execute = AsyncMock(return_value=result)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/payments/webhook", content=body)
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400():
    order_id = str(uuid.uuid4())
    body = _make_webhook_body(order_id)
    db = AsyncMock(spec=AsyncSession)
    # IP check passes (empty list)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=result)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/payments/webhook",
                content=body,
                headers={"crypto-pay-api-signature": "invalidsignature"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_already_completed_returns_200():
    tx = _make_transaction(status=TransactionStatus.completed)
    order_id = str(tx.id)
    body = _make_webhook_body(order_id)

    with patch("app.routers.payments._get_webhook_token", return_value=TOKEN), \
         patch("app.routers.payments._check_webhook_ip", return_value=True), \
         patch("app.routers.payments._verify_webhook_sig", return_value=True), \
         patch("app.routers.payments._load_transaction", return_value=tx):
        db = AsyncMock(spec=AsyncSession)
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                sig = _make_sig(TOKEN, body)
                resp = await c.post("/api/payments/webhook", content=body,
                                    headers={"crypto-pay-api-signature": sig})
        finally:
            app.dependency_overrides.clear()
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webhook_cancel_marks_transaction_failed():
    tx = _make_transaction()
    order_id = str(tx.id)
    body = _make_webhook_body(order_id, status="expired")
    db = AsyncMock(spec=AsyncSession)

    with patch("app.routers.payments._get_webhook_token", return_value=TOKEN), \
         patch("app.routers.payments._check_webhook_ip", return_value=True), \
         patch("app.routers.payments._verify_webhook_sig", return_value=True), \
         patch("app.routers.payments._load_transaction", return_value=tx):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/payments/webhook", content=body,
                                    headers={"crypto-pay-api-signature": _make_sig(TOKEN, body)})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert tx.status == TransactionStatus.failed


@pytest.mark.asyncio
async def test_webhook_paid_success_returns_200():
    """Happy path: paid webhook → complete_payment called → 200 returned."""
    tx = _make_transaction()
    plan = _make_plan()
    order_id = str(tx.id)
    body = _make_webhook_body(order_id, status="paid")
    db = AsyncMock(spec=AsyncSession)

    mock_complete = AsyncMock(return_value=None)

    with patch("app.routers.payments._get_webhook_token", return_value=TOKEN), \
         patch("app.routers.payments._check_webhook_ip", return_value=True), \
         patch("app.routers.payments._verify_webhook_sig", return_value=True), \
         patch("app.routers.payments._load_transaction", return_value=tx), \
         patch("app.routers.payments._load_plan_and_user", return_value=(plan, MagicMock())), \
         patch("app.routers.payments._get_remnawave_client", return_value=MagicMock()), \
         patch("app.routers.payments.complete_payment", mock_complete):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/payments/webhook", content=body,
                                    headers={"crypto-pay-api-signature": _make_sig(TOKEN, body)})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    mock_complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_paid_remnawave_failure_returns_500():
    tx = _make_transaction()
    plan = _make_plan()
    order_id = str(tx.id)
    body = _make_webhook_body(order_id, status="paid")
    db = AsyncMock(spec=AsyncSession)

    import httpx as _httpx

    with patch("app.routers.payments._get_webhook_token", return_value=TOKEN), \
         patch("app.routers.payments._check_webhook_ip", return_value=True), \
         patch("app.routers.payments._verify_webhook_sig", return_value=True), \
         patch("app.routers.payments._load_transaction", return_value=tx), \
         patch("app.routers.payments._load_plan_and_user", return_value=(plan, MagicMock())), \
         patch("app.routers.payments._get_remnawave_client", return_value=MagicMock()), \
         patch("app.routers.payments.complete_payment",
               side_effect=_httpx.RequestError("timeout")), \
         patch("app.routers.payments.send_admin_alert", new=AsyncMock()):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/payments/webhook", content=body,
                                    headers={"crypto-pay-api-signature": _make_sig(TOKEN, body)})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 500

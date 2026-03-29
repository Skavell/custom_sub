import pytest
from datetime import datetime, timezone
from pytest_httpx import HTTPXMock

from app.services.remnawave_client import RemnawaveClient, RemnawaveUser


BASE_URL = "https://remnawave.example.com"
TOKEN = "test-api-token"

SAMPLE_USER_RESPONSE = {
    "uuid": "aaaaaaaa-0000-0000-0000-000000000001",
    "username": "ws_4a1b2c3d",
    "expireAt": "2026-04-10T00:00:00Z",
    "trafficLimitBytes": 32212254720,
    "status": "ACTIVE",
    "subscriptionUrl": "https://sub.example.com/sub/abc123",
    "telegramId": 515172616,
}


@pytest.mark.asyncio
async def test_get_user_returns_user(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/users/aaaaaaaa-0000-0000-0000-000000000001",
        json=SAMPLE_USER_RESPONSE,
    )
    client = RemnawaveClient(BASE_URL, TOKEN)
    user = await client.get_user("aaaaaaaa-0000-0000-0000-000000000001")
    assert user.id == "aaaaaaaa-0000-0000-0000-000000000001"
    assert user.subscription_url == "https://sub.example.com/sub/abc123"
    assert user.traffic_limit_bytes == 32212254720
    assert user.telegram_id == 515172616


@pytest.mark.asyncio
async def test_get_user_by_telegram_id_found(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/users/by-telegram-id/515172616",
        json=SAMPLE_USER_RESPONSE,
    )
    client = RemnawaveClient(BASE_URL, TOKEN)
    user = await client.get_user_by_telegram_id(515172616)
    assert user is not None
    assert user.id == "aaaaaaaa-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_get_user_by_telegram_id_not_found(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/users/by-telegram-id/99999",
        status_code=404,
    )
    client = RemnawaveClient(BASE_URL, TOKEN)
    user = await client.get_user_by_telegram_id(99999)
    assert user is None


@pytest.mark.asyncio
async def test_create_user_returns_user(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/users",
        json=SAMPLE_USER_RESPONSE,
        status_code=201,
    )
    client = RemnawaveClient(BASE_URL, TOKEN)
    user = await client.create_user(
        username="ws_4a1b2c3d",
        traffic_limit_bytes=32212254720,
        expire_at="2026-04-10T00:00:00Z",
        squad_ids=["squad-uuid-1"],
        telegram_id=515172616,
        description="@skavellion_user",
    )
    assert user.id == "aaaaaaaa-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_update_user(httpx_mock: HTTPXMock):
    updated = {**SAMPLE_USER_RESPONSE, "trafficLimitBytes": 0}
    httpx_mock.add_response(
        method="PATCH",
        url=f"{BASE_URL}/users/aaaaaaaa-0000-0000-0000-000000000001",
        json=updated,
    )
    client = RemnawaveClient(BASE_URL, TOKEN)
    user = await client.update_user(
        "aaaaaaaa-0000-0000-0000-000000000001",
        traffic_limit_bytes=0,
        expire_at="2026-05-10T00:00:00Z",
    )
    assert user.traffic_limit_bytes == 0

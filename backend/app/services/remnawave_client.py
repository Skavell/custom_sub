from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)
_TIMEOUT = httpx.Timeout(10.0)


@dataclass
class RemnawaveUser:
    id: int
    short_uuid: str
    username: str
    expire_at: datetime
    traffic_limit_bytes: int
    status: str
    subscription_url: str
    telegram_id: int | None
    used_traffic_bytes: int
    first_connected_at: datetime | None


def _response_object(data: dict[str, Any]) -> dict[str, Any]:
    response = data.get("response")
    return response if isinstance(response, dict) else data


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _parse_user(data: dict[str, Any]) -> RemnawaveUser:
    data = _response_object(data)
    traffic = data.get("userTraffic") or {}
    used_traffic = traffic.get("usedTrafficBytes", data.get("usedTrafficBytes", 0)) or 0
    first_connected = traffic.get("firstConnectedAt", data.get("firstConnectedAt"))
    expire_at = _parse_datetime(data["expireAt"])
    if expire_at is None:
        raise ValueError("Remnawave user response is missing expireAt")
    return RemnawaveUser(
        id=int(data["id"]),
        short_uuid=data.get("shortUuid", ""),
        username=data["username"],
        expire_at=expire_at,
        traffic_limit_bytes=data.get("trafficLimitBytes") or 0,
        status=data.get("status", "ACTIVE"),
        subscription_url=data.get("subscriptionUrl", ""),
        telegram_id=data.get("telegramId"),
        used_traffic_bytes=used_traffic,
        first_connected_at=_parse_datetime(first_connected),
    )


class RemnawaveClient:
    """Client for the Remnawave v3 user API, where users have numeric ids."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def get_user(self, remnawave_user_id: int) -> RemnawaveUser:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            response = await http.get(f"{self._base}/users/{remnawave_user_id}", headers=self._headers)
            response.raise_for_status()
            return _parse_user(response.json())

    async def get_user_by_username(self, username: str) -> RemnawaveUser | None:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            response = await http.get(f"{self._base}/users/by-username/{username}", headers=self._headers)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return _parse_user(response.json())

    async def get_user_by_short_uuid(self, short_uuid: str) -> RemnawaveUser | None:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            response = await http.get(f"{self._base}/users/by-short-uuid/{short_uuid}", headers=self._headers)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return _parse_user(response.json())

    async def get_user_by_telegram_id(self, telegram_id: int) -> RemnawaveUser | None:
        """v3 replacement for the removed /users/by-telegram-id endpoint."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            response = await http.get(
                f"{self._base}/users/stream", headers=self._headers,
                params={"telegramId": telegram_id, "size": 1000},
            )
            response.raise_for_status()
            raw_payload = response.json()
            payload = _response_object(raw_payload)
            users = raw_payload.get("response") if isinstance(raw_payload.get("response"), list) else payload.get("items", payload.get("users", []))
            if not users:
                return None
            if len(users) > 1:
                logger.warning("Multiple Remnawave users found for Telegram id %s", telegram_id)
            return _parse_user(users[0])

    async def create_user(self, username: str, traffic_limit_bytes: int, expire_at: str,
                          internal_squad_uuids: list[str] | None = None,
                          external_squad_uuid: str | None = None, telegram_id: int | None = None,
                          description: str | None = None) -> RemnawaveUser:
        payload: dict[str, Any] = {"username": username, "trafficLimitBytes": traffic_limit_bytes, "expireAt": expire_at}
        if internal_squad_uuids:
            payload["activeInternalSquads"] = internal_squad_uuids
        if external_squad_uuid:
            payload["externalSquadUuid"] = external_squad_uuid
        if telegram_id is not None:
            payload["telegramId"] = telegram_id
        if description:
            payload["description"] = description
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            response = await http.post(f"{self._base}/users", headers=self._headers, json=payload)
            response.raise_for_status()
            return _parse_user(response.json())

    async def update_user(self, remnawave_user_id: int, traffic_limit_bytes: int | None = None,
                          expire_at: str | None = None, internal_squad_uuids: list[str] | None = None,
                          external_squad_uuid: str | None = None, telegram_id: int | None = None,
                          description: str | None = None) -> RemnawaveUser:
        payload: dict[str, Any] = {"id": remnawave_user_id}
        if traffic_limit_bytes is not None:
            payload["trafficLimitBytes"] = traffic_limit_bytes
        if expire_at is not None:
            payload["expireAt"] = expire_at
        if internal_squad_uuids is not None:
            payload["activeInternalSquads"] = internal_squad_uuids
        if external_squad_uuid is not None:
            payload["externalSquadUuid"] = external_squad_uuid
        if telegram_id is not None:
            payload["telegramId"] = telegram_id
        if description is not None:
            payload["description"] = description
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            response = await http.patch(f"{self._base}/users", headers=self._headers, json=payload)
            response.raise_for_status()
            return _parse_user(response.json())

    async def delete_user(self, remnawave_user_id: int) -> None:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            response = await http.delete(f"{self._base}/users/{remnawave_user_id}", headers=self._headers)
            response.raise_for_status()

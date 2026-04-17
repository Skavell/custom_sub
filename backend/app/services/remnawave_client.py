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
    id: str
    username: str
    expire_at: datetime
    traffic_limit_bytes: int  # 0 = unlimited
    status: str               # "ACTIVE" | "DISABLED"
    subscription_url: str
    telegram_id: int | None


def _parse_user(data: dict[str, Any]) -> RemnawaveUser:
    if "response" in data:
        data = data["response"]
    return RemnawaveUser(
        id=data["uuid"],
        username=data["username"],
        expire_at=datetime.fromisoformat(data["expireAt"].replace("Z", "+00:00")),
        traffic_limit_bytes=data.get("trafficLimitBytes") or 0,
        status=data.get("status", "ACTIVE"),
        subscription_url=data.get("subscriptionUrl", ""),
        telegram_id=data.get("telegramId"),
    )


class RemnawaveClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def get_user(self, remnawave_uuid: str) -> RemnawaveUser:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.get(
                f"{self._base}/users/{remnawave_uuid}", headers=self._headers
            )
            resp.raise_for_status()
            return _parse_user(resp.json())

    async def get_user_by_telegram_id(self, telegram_id: int) -> RemnawaveUser | None:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.get(
                f"{self._base}/users/by-telegram-id/{telegram_id}",
                headers=self._headers,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            # API returns {"response": [...]} — array, not single object
            if "response" in data:
                items = data["response"]
                if not items:
                    return None
                return _parse_user(items[0])
            return _parse_user(data)

    async def create_user(
        self,
        username: str,
        traffic_limit_bytes: int,
        expire_at: str,
        internal_squad_uuids: list[str] | None = None,
        external_squad_uuid: str | None = None,
        telegram_id: int | None = None,
        description: str | None = None,
    ) -> RemnawaveUser:
        payload: dict[str, Any] = {
            "username": username,
            "trafficLimitBytes": traffic_limit_bytes,
            "expireAt": expire_at,
        }
        if internal_squad_uuids:
            payload["activeInternalSquads"] = internal_squad_uuids
        if external_squad_uuid:
            payload["externalSquadUuid"] = external_squad_uuid
        if telegram_id is not None:
            payload["telegramId"] = telegram_id
        if description:
            payload["description"] = description
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.post(f"{self._base}/users", headers=self._headers, json=payload)
            logger.error("Remnawave create_user status=%s body=%s", resp.status_code, resp.text)
            resp.raise_for_status()
            return _parse_user(resp.json())

    async def update_user(
        self,
        remnawave_uuid: str,
        traffic_limit_bytes: int | None = None,
        expire_at: str | None = None,
        internal_squad_uuids: list[str] | None = None,
        external_squad_uuid: str | None = None,
        telegram_id: int | None = None,
        description: str | None = None,
    ) -> RemnawaveUser:
        payload: dict[str, Any] = {"uuid": remnawave_uuid}
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
            resp = await http.patch(
                f"{self._base}/users",
                headers=self._headers,
                json=payload,
            )
            logger.error("Remnawave update_user status=%s body=%s", resp.status_code, resp.text)
            resp.raise_for_status()
            return _parse_user(resp.json())

    async def delete_user(self, remnawave_uuid: str) -> None:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.delete(
                f"{self._base}/users/{remnawave_uuid}",
                headers=self._headers,
            )
            resp.raise_for_status()

# backend/app/services/auth/oauth/telegram_oidc.py
from dataclasses import dataclass
import httpx

TOKEN_URL = "https://oauth.telegram.org/auth/token"


@dataclass
class TelegramOIDCUser:
    id: int
    first_name: str
    last_name: str | None
    username: str | None
    photo_url: str | None


async def exchange_telegram_oidc_code(
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> TelegramOIDCUser:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "bot_id": client_id,
                "client_secret": client_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    user = data.get("user", data)
    return TelegramOIDCUser(
        id=int(user["id"]),
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name"),
        username=user.get("username"),
        photo_url=user.get("photo_url"),
    )

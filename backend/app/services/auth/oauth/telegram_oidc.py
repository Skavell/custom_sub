import httpx

from app.services.auth.oauth.telegram import TelegramUser

TOKEN_URL = "https://oauth.telegram.org/auth/token"


async def exchange_telegram_oidc_code(
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> TelegramUser:
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

    # Telegram may return user data nested under "user" or at root level
    user = data.get("user", data)
    if "id" not in user:
        raise ValueError("Invalid Telegram OIDC response: missing user ID")
    return TelegramUser(
        id=int(user["id"]),
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name"),
        username=user.get("username"),
        photo_url=user.get("photo_url"),
    )

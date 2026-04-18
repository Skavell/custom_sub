import base64
import json
import httpx

from app.services.auth.oauth.telegram import TelegramUser

TOKEN_URL = "https://oauth.telegram.org/token"


def _decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without signature verification.

    Safe here because the token was received directly from Telegram's
    token endpoint over HTTPS — we trust the source, not the signature.
    """
    payload_b64 = token.split(".")[1]
    # Restore base64 padding
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


async def exchange_telegram_oidc_code(
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> TelegramUser:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            headers={"Authorization": f"Basic {credentials}"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    id_token = data.get("id_token")
    if not id_token:
        raise ValueError("No id_token in Telegram OIDC response")

    claims = _decode_jwt_payload(id_token)

    user_id = claims.get("id") or claims.get("sub")
    if not user_id:
        raise ValueError("Invalid Telegram OIDC token: missing id/sub claim")

    # Split full name into first/last; fall back to given_name/family_name if present
    first_name = claims.get("given_name") or claims.get("name", "").split(" ", 1)[0]
    last_name = claims.get("family_name") or (
        claims.get("name", "").split(" ", 1)[1]
        if " " in claims.get("name", "")
        else None
    )

    return TelegramUser(
        id=int(user_id),
        first_name=first_name,
        last_name=last_name,
        username=claims.get("preferred_username") or claims.get("username"),
        photo_url=claims.get("picture"),
        phone_number=claims.get("phone_number"),
    )

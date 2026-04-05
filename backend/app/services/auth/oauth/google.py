from dataclasses import dataclass
import httpx


@dataclass
class GoogleUser:
    id: str
    email: str
    name: str
    picture: str | None


async def exchange_google_code(code: str, redirect_uri: str, client_id: str, client_secret: str) -> GoogleUser:
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_resp.raise_for_status()
        info = userinfo_resp.json()

    return GoogleUser(
        id=info["id"],
        email=info["email"],
        name=info.get("name", info["email"]),
        picture=info.get("picture"),
    )

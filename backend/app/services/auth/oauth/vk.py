from dataclasses import dataclass
import httpx


@dataclass
class VKUser:
    id: str
    first_name: str
    last_name: str
    avatar: str | None


async def exchange_vk_code(code: str, redirect_uri: str, device_id: str, state: str, client_id: str, client_secret: str) -> VKUser:
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://id.vk.com/oauth2/auth",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "device_id": device_id,
                "state": state,
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

        info_resp = await client.post(
            "https://id.vk.com/oauth2/user_info",
            data={"access_token": token_data["access_token"], "client_id": client_id},
        )
        info_resp.raise_for_status()
        user = info_resp.json()["user"]

    return VKUser(
        id=str(user["user_id"]),
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name", ""),
        avatar=user.get("avatar"),
    )

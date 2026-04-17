import hashlib
import hmac
import time
from dataclasses import dataclass


@dataclass
class TelegramUser:
    id: int
    first_name: str
    last_name: str | None
    username: str | None
    photo_url: str | None


def verify_telegram_data(data: dict, bot_token: str, max_age_seconds: int = 86400) -> dict:
    received_hash = data.get("hash", "")
    auth_date = int(data.get("auth_date", 0))

    if time.time() - auth_date > max_age_seconds:
        raise ValueError("Telegram auth data expired")

    check_data = {k: v for k, v in data.items() if k != "hash"}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(check_data.items()))
    secret = hashlib.sha256(bot_token.strip().encode()).digest()
    expected_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Invalid Telegram hash")

    return data


def parse_telegram_user(data: dict) -> TelegramUser:
    return TelegramUser(
        id=data["id"],
        first_name=data["first_name"],
        last_name=data.get("last_name"),
        username=data.get("username"),
        photo_url=data.get("photo_url"),
    )

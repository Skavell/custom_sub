import hashlib
import hmac
import time
import pytest
from app.services.auth.oauth.telegram import verify_telegram_data


def make_valid_data(bot_token: str = "test:token") -> dict:
    data = {
        "id": "123456789",
        "first_name": "Ivan",
        "auth_date": str(int(time.time())),
    }
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hashlib.sha256(bot_token.encode()).digest()
    hash_val = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return {**data, "hash": hash_val}


def test_valid_telegram_data_passes():
    data = make_valid_data("test:token")
    result = verify_telegram_data(data, bot_token="test:token")
    assert result["id"] == "123456789"


def test_tampered_data_rejected():
    data = make_valid_data("test:token")
    data["first_name"] = "Hacker"
    with pytest.raises(ValueError, match="Invalid"):
        verify_telegram_data(data, bot_token="test:token")


def test_expired_auth_date_rejected():
    data = make_valid_data("test:token")
    data["auth_date"] = "1000000000"  # way in the past
    # recompute valid hash for this tampered data
    check_data = {k: v for k, v in data.items() if k != "hash"}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(check_data.items()))
    secret = hashlib.sha256("test:token".encode()).digest()
    data["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    with pytest.raises(ValueError, match="expired"):
        verify_telegram_data(data, bot_token="test:token")

import pytest
from datetime import timedelta
from app.services.auth.jwt_service import (
    create_access_token,
    create_refresh_token,
    verify_token,
    TokenType,
)


def test_access_token_roundtrip():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(user_id)
    payload = verify_token(token, TokenType.ACCESS)
    assert payload["sub"] == user_id


def test_refresh_token_roundtrip():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_refresh_token(user_id)
    payload = verify_token(token, TokenType.REFRESH)
    assert payload["sub"] == user_id


def test_access_token_rejected_as_refresh():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(user_id)
    with pytest.raises(ValueError, match="Invalid token type"):
        verify_token(token, TokenType.REFRESH)


def test_expired_token_raises():
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(user_id, expires_delta=timedelta(seconds=-1))
    with pytest.raises(ValueError, match="expired"):
        verify_token(token, TokenType.ACCESS)

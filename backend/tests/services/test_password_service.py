from app.services.auth.password_service import hash_password, verify_password


def test_hash_and_verify():
    password = "MySecurePassword123!"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_wrong_password_rejected():
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_hash_is_not_plaintext():
    password = "secret"
    hashed = hash_password(password)
    assert hashed != password

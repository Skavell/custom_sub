import pytest
from pydantic import ValidationError
from app.schemas.auth import EmailRegisterRequest, LinkEmailRequest


@pytest.mark.parametrize("password,error_fragment", [
    ("short1A", "8 символов"),          # too short
    ("alllowercase1", "заглавную"),     # no uppercase
    ("ALLUPPERCASE1", "строчную"),      # no lowercase
    ("NoDigitsHere", "цифру"),          # no digit
])
def test_weak_passwords_rejected_in_register(password, error_fragment):
    with pytest.raises(ValidationError) as exc:
        EmailRegisterRequest(email="a@b.com", password=password, display_name="Name")
    assert error_fragment in str(exc.value)


def test_strong_password_accepted():
    req = EmailRegisterRequest(email="a@b.com", password="Secure1Pass", display_name="Name")
    assert req.password == "Secure1Pass"


def test_weak_password_rejected_in_link_email():
    with pytest.raises(ValidationError) as exc:
        LinkEmailRequest(email="a@b.com", password="weakpass")
    assert "заглавную" in str(exc.value)

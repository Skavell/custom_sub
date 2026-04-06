from app.schemas.payment import PaymentProviderInfo, CreatePaymentRequest


def test_payment_provider_info_schema():
    info = PaymentProviderInfo(name="cryptobot", label="CryptoBot", is_active=True)
    assert info.name == "cryptobot"
    assert info.label == "CryptoBot"
    assert info.is_active is True


def test_create_payment_request_provider_defaults_to_cryptobot():
    req = CreatePaymentRequest(plan_id="00000000-0000-0000-0000-000000000001")
    assert req.provider == "cryptobot"


def test_create_payment_request_provider_explicit():
    req = CreatePaymentRequest(
        plan_id="00000000-0000-0000-0000-000000000001",
        provider="some_provider",
    )
    assert req.provider == "some_provider"

from __future__ import annotations
import hashlib
import hmac as _hmac
import logging

import httpx

from app.services.payment_providers.base import InvoiceResult, PaymentProvider

logger = logging.getLogger(__name__)
_TIMEOUT = httpx.Timeout(10.0)


class CryptoBotProvider(PaymentProvider):
    BASE_URL = "https://pay.crypt.bot/api"

    def __init__(self, token: str, usdt_rate: float) -> None:
        self._token = token
        self._rate = usdt_rate

    @property
    def name(self) -> str:
        return "cryptobot"

    async def create_invoice(
        self, amount_rub: int, order_id: str, description: str
    ) -> InvoiceResult:
        usdt_amount = str(round(amount_rub / self._rate, 2))
        body = {
            "asset": "USDT",
            "amount": usdt_amount,
            "description": description,
            "payload": order_id,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.post(
                f"{self.BASE_URL}/createInvoice",
                json=body,
                headers={"Crypto-Pay-API-Token": self._token},
            )
            resp.raise_for_status()
            data = resp.json()
        if not data.get("ok"):
            raise ValueError(f"CryptoBot API error: {data.get('error', data)}")
        result = data["result"]
        return InvoiceResult(
            payment_url=result["bot_invoice_url"],
            external_id=str(result["invoice_id"]),
        )

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        secret = hashlib.sha256(self._token.encode()).digest()
        signature = headers.get("crypto-pay-api-signature", "")
        expected = _hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        return _hmac.compare_digest(expected.lower(), signature.lower())

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class InvoiceResult:
    payment_url: str   # Link shown to user (t.me/CryptoBot?start=IV...)
    external_id: str   # Provider's invoice ID → transaction.external_payment_id


class PaymentProvider(ABC):
    @abstractmethod
    async def create_invoice(
        self,
        amount_rub: int,
        order_id: str,
        description: str,
    ) -> InvoiceResult: ...

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

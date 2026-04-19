from __future__ import annotations
import logging

import httpx

logger = logging.getLogger(__name__)


async def get_support_settings(db) -> dict | None:  # pragma: no cover – implemented in Task 9
    return None


async def send_admin_support_notification(  # pragma: no cover – implemented in Task 9
    token: str,
    chat_id: str,
    ticket_number: int,
    user_display_name: str,
    user_email: str | None,
    subscription_status,
    text: str,
) -> int | None:
    return None


async def send_admin_alert(
    token: str | None, chat_id: str | None, message: str
) -> None:
    """Fire-and-forget Telegram alert. No-ops on missing token/chat_id.
    Swallows all exceptions — must never block the main flow.
    """
    if not token or not chat_id:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            await http.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
            )
    except Exception as exc:
        logger.warning("Telegram alert failed (non-blocking): %s", exc)

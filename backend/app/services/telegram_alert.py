from __future__ import annotations
import logging

import httpx

logger = logging.getLogger(__name__)


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


async def send_admin_support_notification(
    token: str,
    chat_id: str,
    ticket_number: int,
    user_display_name: str,
    user_email: str | None,
    subscription_status: str | None,
    text: str,
) -> int | None:
    """Отправляет уведомление администратору о новом сообщении в обращении.
    Возвращает message_id отправленного сообщения."""
    email_str = user_email or "нет email"
    sub_str = subscription_status or "нет подписки"
    message_text = (
        f"#ОБР-{ticket_number} · {user_display_name}\n"
        f"{email_str} · {sub_str}\n\n"
        f"{text}\n\n"
        f"↩ Ответь на это сообщение чтобы ответить в обращении"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message_text},
            )
            if resp.is_success:
                data = resp.json()
                return data.get("result", {}).get("message_id")
    except Exception:
        logger.warning("Failed to send admin support notification")
    return None


async def send_user_telegram_notification(
    token: str,
    telegram_chat_id: str,
    ticket_number: int,
    subject: str,
    reply_text: str,
    ticket_url: str,
) -> None:
    """Отправляет пользователю Telegram-уведомление об ответе в обращении."""
    text = (
        f"Ответ на твоё обращение #ОБР-{ticket_number}\n"
        f"«{subject}»\n\n"
        f"{reply_text}"
    )
    inline_keyboard = {
        "inline_keyboard": [[{
            "text": "💬 Открыть обращение →",
            "url": ticket_url,
        }]]
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": telegram_chat_id,
                    "text": text,
                    "reply_markup": inline_keyboard,
                },
            )
    except Exception:
        logger.warning("Failed to send user Telegram notification")


async def get_support_settings(db) -> dict | None:
    """Читает настройки Telegram бота из БД. Возвращает None если не настроены."""
    from app.services.setting_service import get_setting_decrypted

    token = await get_setting_decrypted(db, "telegram_bot_token")
    chat_id = await get_setting_decrypted(db, "telegram_support_chat_id")
    if not token or not chat_id:
        return None
    return {"token": token, "chat_id": chat_id}

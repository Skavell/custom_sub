"""Telegram bot listener — принимает Reply-ответы администратора и добавляет их в тикеты."""
import asyncio
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_polling_task: asyncio.Task | None = None
_last_update_id: int = 0


async def _get_updates(token: str, offset: int, timeout: int = 30) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=timeout + 5.0) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": timeout, "allowed_updates": ["message"]},
            )
            if resp.is_success:
                return resp.json().get("result", [])
    except Exception as e:
        logger.warning(f"getUpdates failed: {e}")
    return []


async def _handle_reply(token: str, update: dict) -> None:
    message = update.get("message", {})
    reply_to = message.get("reply_to_message")
    text = message.get("text", "").strip()

    if not reply_to or not text:
        return

    reply_to_message_id = reply_to.get("message_id")
    if not reply_to_message_id:
        return

    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.support_message import SupportMessage
    from app.models.support_ticket import SupportTicket
    from app.services.user_notifier import notify_user_on_reply

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SupportMessage).where(
                SupportMessage.telegram_message_id == reply_to_message_id
            )
        )
        original_message = result.scalar_one_or_none()
        if not original_message:
            logger.debug(f"No message found for telegram_message_id={reply_to_message_id}")
            return

        ticket_result = await db.execute(
            select(SupportTicket).where(SupportTicket.id == original_message.ticket_id)
        )
        ticket = ticket_result.scalar_one_or_none()
        if not ticket or ticket.status == "closed":
            return

        admin_message = SupportMessage(
            ticket_id=ticket.id,
            author_type="admin",
            text=text,
            is_read_by_user=False,
        )
        ticket.updated_at = datetime.now(timezone.utc)
        db.add(admin_message)
        await db.commit()
        await db.refresh(admin_message)

        await notify_user_on_reply(db=db, ticket=ticket, reply_text=text)

    logger.info(f"Admin reply added to ticket #{ticket.number} via Telegram")


async def _polling_loop(token: str, admin_chat_id: str) -> None:
    global _last_update_id
    logger.info("Telegram bot polling started")
    while True:
        try:
            updates = await _get_updates(token, offset=_last_update_id + 1)
            for update in updates:
                _last_update_id = max(_last_update_id, update["update_id"])
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                if chat_id != admin_chat_id:
                    continue
                await _handle_reply(token, update)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Polling loop error: {e}")
            await asyncio.sleep(5)


async def start_polling(token: str, admin_chat_id: str) -> None:
    global _polling_task
    if _polling_task and not _polling_task.done():
        return
    _polling_task = asyncio.create_task(_polling_loop(token, admin_chat_id))


async def stop_polling() -> None:
    global _polling_task
    if _polling_task and not _polling_task.done():
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
    _polling_task = None

"""Уведомляет пользователя об ответе в обращении (Telegram приоритет, иначе Email)."""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_config
from app.models.auth_provider import AuthProvider, ProviderType
from app.models.support_ticket import SupportTicket
from app.services.setting_service import get_setting_decrypted

logger = logging.getLogger(__name__)


async def notify_user_on_reply(db: AsyncSession, ticket: SupportTicket, reply_text: str) -> None:
    frontend_url = app_config.frontend_url.rstrip("/")
    ticket_url = f"{frontend_url}/support/{ticket.id}"

    tg_result = await db.execute(
        select(AuthProvider).where(
            AuthProvider.user_id == ticket.user_id,
            AuthProvider.provider == ProviderType.telegram,
        )
    )
    tg_provider = tg_result.scalar_one_or_none()
    token = await get_setting_decrypted(db, "telegram_bot_token")

    if tg_provider and tg_provider.provider_user_id and token:
        from app.services.telegram_alert import send_user_telegram_notification
        await send_user_telegram_notification(
            token=token,
            telegram_chat_id=tg_provider.provider_user_id,
            ticket_number=ticket.number,
            subject=ticket.subject,
            reply_text=reply_text,
            ticket_url=ticket_url,
        )
        return

    email_result = await db.execute(
        select(AuthProvider).where(
            AuthProvider.user_id == ticket.user_id,
            AuthProvider.provider == ProviderType.email,
        )
    )
    email_provider = email_result.scalar_one_or_none()

    resend_api_key = await get_setting_decrypted(db, "resend_api_key")
    email_from_address = await get_setting_decrypted(db, "email_from_address")
    email_from_name = await get_setting_decrypted(db, "email_from_name") or "Поддержка"

    if email_provider and resend_api_key and email_from_address:
        from app.services.email_service import send_ticket_reply_email
        from app.models.user import User
        user_result = await db.execute(select(User).where(User.id == ticket.user_id))
        user = user_result.scalar_one_or_none()
        try:
            await send_ticket_reply_email(
                api_key=resend_api_key,
                from_address=email_from_address,
                from_name=email_from_name,
                to_email=email_provider.provider_user_id,
                to_name=user.display_name if user else "Пользователь",
                ticket_number=ticket.number,
                subject=ticket.subject,
                reply_text=reply_text,
                ticket_url=ticket_url,
            )
        except Exception:
            logger.warning("Failed to send ticket reply email")

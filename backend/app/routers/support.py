import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import sqlalchemy as sa
from app.database import get_db
from app.deps import get_current_user
from app.models.support_ticket import SupportTicket
from app.models.support_message import SupportMessage
from app.schemas.support import (
    CreateTicketRequest,
    AddMessageRequest,
    SupportTicketOut,
    SupportTicketDetailOut,
    SupportMessageOut,
)
from app.services.telegram_alert import get_support_settings, send_admin_support_notification
from app.services.user_notifier import notify_user_on_reply
from app.models.user import User

router = APIRouter(prefix="/api/support/tickets", tags=["support"], redirect_slashes=False)


def _ticket_out(ticket: SupportTicket, unread_count: int = 0) -> SupportTicketOut:
    return SupportTicketOut(
        id=ticket.id,
        number=ticket.number,
        subject=ticket.subject,
        status=ticket.status,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        unread_count=unread_count,
    )


@router.get("", response_model=list[SupportTicketOut])
async def list_my_tickets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SupportTicketOut]:
    result = await db.execute(
        select(SupportTicket)
        .where(SupportTicket.user_id == current_user.id)
        .order_by(SupportTicket.updated_at.desc())
    )
    tickets = result.scalars().all()

    ticket_list = []
    for ticket in tickets:
        unread_result = await db.execute(
            select(func.count(SupportMessage.id))
            .where(
                SupportMessage.ticket_id == ticket.id,
                SupportMessage.author_type == "admin",
                SupportMessage.is_read_by_user == False,  # noqa: E712
            )
        )
        unread_count = unread_result.scalar() or 0
        ticket_list.append(_ticket_out(ticket, unread_count))

    return ticket_list


@router.post("", response_model=SupportTicketDetailOut, status_code=201)
async def create_ticket(
    body: CreateTicketRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketDetailOut:
    next_number = int(await db.scalar(sa.text("SELECT nextval('support_ticket_number_seq')")))

    now = datetime.now(timezone.utc)
    ticket = SupportTicket(
        id=uuid.uuid4(),
        user_id=current_user.id,
        number=next_number,
        subject=body.subject,
        status="open",
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    await db.flush()

    message = SupportMessage(
        id=uuid.uuid4(),
        ticket_id=ticket.id,
        author_type="user",
        text=body.text,
        is_read_by_user=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    await db.commit()
    await db.refresh(ticket)
    await db.refresh(message)

    settings = await get_support_settings(db)
    if settings:
        tg_message_id = await send_admin_support_notification(
            token=settings["token"],
            chat_id=settings["chat_id"],
            ticket_number=ticket.number,
            user_display_name=current_user.display_name,
            user_email=_get_user_email(current_user),
            subscription_status=None,
            text=body.text,
        )
        if tg_message_id:
            message.telegram_message_id = tg_message_id
            await db.commit()

    return SupportTicketDetailOut(
        id=ticket.id,
        number=ticket.number,
        subject=ticket.subject,
        status=ticket.status,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        messages=[SupportMessageOut(
            id=message.id,
            author_type=message.author_type,
            text=message.text,
            created_at=message.created_at,
        )],
    )


@router.get("/{ticket_id}", response_model=SupportTicketDetailOut)
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketDetailOut:
    result = await db.execute(
        select(SupportTicket)
        .where(SupportTicket.id == ticket_id, SupportTicket.user_id == current_user.id)
        .options(selectinload(SupportTicket.messages))
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Обращение не найдено")

    for msg in ticket.messages:
        if msg.author_type == "admin" and not msg.is_read_by_user:
            msg.is_read_by_user = True
    await db.commit()

    return SupportTicketDetailOut(
        id=ticket.id,
        number=ticket.number,
        subject=ticket.subject,
        status=ticket.status,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        messages=[SupportMessageOut(
            id=m.id, author_type=m.author_type, text=m.text, created_at=m.created_at
        ) for m in ticket.messages],
    )


@router.post("/{ticket_id}/messages", response_model=SupportMessageOut, status_code=201)
async def add_message(
    ticket_id: uuid.UUID,
    body: AddMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SupportMessageOut:
    result = await db.execute(
        select(SupportTicket)
        .where(SupportTicket.id == ticket_id, SupportTicket.user_id == current_user.id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    if ticket.status == "closed":
        raise HTTPException(status_code=400, detail="Обращение закрыто")

    message = SupportMessage(
        id=uuid.uuid4(),
        ticket_id=ticket.id,
        author_type="user",
        text=body.text,
        is_read_by_user=True,
        created_at=datetime.now(timezone.utc),
    )
    ticket.updated_at = datetime.now(timezone.utc)
    db.add(message)
    await db.commit()
    await db.refresh(message)

    settings = await get_support_settings(db)
    if settings:
        tg_message_id = await send_admin_support_notification(
            token=settings["token"],
            chat_id=settings["chat_id"],
            ticket_number=ticket.number,
            user_display_name=current_user.display_name,
            user_email=_get_user_email(current_user),
            subscription_status=None,
            text=body.text,
        )
        if tg_message_id:
            message.telegram_message_id = tg_message_id
            await db.commit()

    return SupportMessageOut(
        id=message.id, author_type=message.author_type,
        text=message.text, created_at=message.created_at,
    )


def _get_user_email(user: User) -> str | None:
    for provider in getattr(user, 'auth_providers', []):
        if provider.provider == 'email':
            return provider.provider_user_id
    return None

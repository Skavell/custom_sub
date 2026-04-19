from __future__ import annotations
import httpx

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT = httpx.Timeout(10.0)


async def send_verification_email(
    api_key: str,
    from_address: str,
    from_name: str,
    to_email: str,
    verify_url: str,
) -> None:
    """Send email verification link via Resend REST API."""
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2>Подтверждение email</h2>
      <p>Нажмите кнопку ниже, чтобы подтвердить ваш email-адрес.</p>
      <a href="{verify_url}"
         style="display:inline-block;padding:12px 24px;background:#06b6d4;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">
        Подтвердить email
      </a>
      <p style="color:#888;font-size:12px;margin-top:24px">
        Ссылка действительна 24 часа. Если вы не запрашивали подтверждение — проигнорируйте это письмо.
      </p>
    </div>
    """
    payload = {
        "from": f"{from_name} <{from_address}>",
        "to": [to_email],
        "subject": "Подтвердите ваш email",
        "html": html,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()


async def send_reset_email(
    api_key: str,
    from_address: str,
    from_name: str,
    to_email: str,
    reset_url: str,
) -> None:
    """Send password reset link via Resend REST API."""
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2>Сброс пароля</h2>
      <p>Нажмите кнопку ниже, чтобы сбросить пароль. Ссылка действительна 1 час.</p>
      <a href="{reset_url}"
         style="display:inline-block;padding:12px 24px;background:#06b6d4;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">
        Сбросить пароль
      </a>
      <p style="color:#888;font-size:12px;margin-top:24px">
        Если вы не запрашивали сброс пароля — проигнорируйте это письмо.
      </p>
    </div>
    """
    payload = {
        "from": f"{from_name} <{from_address}>",
        "to": [to_email],
        "subject": "Сброс пароля",
        "html": html,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()


async def send_ticket_reply_email(
    api_key: str,
    from_address: str,
    from_name: str,
    to_email: str,
    to_name: str,
    ticket_number: int,
    subject: str,
    reply_text: str,
    ticket_url: str,
) -> None:
    """Отправляет email-уведомление пользователю об ответе в обращении."""
    html_body = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:24px">
      <h2 style="font-size:18px;margin-bottom:8px">Привет, {to_name}!</h2>
      <p style="color:#64748b;margin-bottom:16px">
        Мы ответили на твоё обращение <strong>#ОБР-{ticket_number}</strong>
        «{subject}»:
      </p>
      <div style="background:#f8fafc;border-left:3px solid #0ea5e9;
                  border-radius:4px;padding:12px 16px;margin-bottom:20px">
        <p style="margin:0;color:#1e293b;line-height:1.6">{reply_text}</p>
      </div>
      <a href="{ticket_url}"
         style="display:block;background:#0ea5e9;color:white;text-align:center;
                padding:12px;border-radius:8px;text-decoration:none;font-weight:600">
        Открыть обращение
      </a>
      <p style="color:#94a3b8;font-size:12px;margin-top:20px">
        Не отвечай на это письмо — перейди по кнопке выше чтобы ответить в обращении.
      </p>
    </div>
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": f"{from_name} <{from_address}>",
                "to": [to_email],
                "subject": f"Ответ на обращение #ОБР-{ticket_number}",
                "html": html_body,
            },
        )
        resp.raise_for_status()

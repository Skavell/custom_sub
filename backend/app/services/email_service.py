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

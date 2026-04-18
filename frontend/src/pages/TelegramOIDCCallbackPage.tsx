import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export default function TelegramOIDCCallbackPage() {
  const navigate = useNavigate();
  const called = useRef(false);

  useEffect(() => {
    if (called.current) return;
    called.current = true;

    const params = new URLSearchParams(window.location.search);
    const error = params.get("error");
    const code = params.get("code");

    if (error || !code) {
      navigate("/login?error=telegram_oidc_failed");
      return;
    }

    const redirectUri = `${window.location.origin}/auth/telegram/callback`;

    const doAuth = async () => {
      try {
        await api.post("/api/auth/oauth/telegram-oidc", { code, redirect_uri: redirectUri });
        navigate("/");
      } catch {
        navigate("/login?error=telegram_oidc_failed");
      }
    };

    doAuth();
  }, [navigate]);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <p className="text-text-secondary text-sm">Вход через Telegram...</p>
    </div>
  );
}

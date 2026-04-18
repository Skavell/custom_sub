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
      navigate("/login?error=telegram_oidc_failed", { replace: true });
      return;
    }

    const redirectUri = `${window.location.origin}/auth/telegram/callback`;

    const doAuth = async () => {
      try {
        await api.post("/api/auth/oauth/telegram-oidc", { code, redirect_uri: redirectUri });
        navigate("/", { replace: true });
      } catch (e) {
        console.error("Telegram OIDC failed", e);
        navigate("/login?error=telegram_oidc_failed", { replace: true });
      }
    };

    doAuth();
  }, [navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
    </div>
  );
}

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import type { OAuthConfigResponse } from '@/types/api'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined
const VK_CLIENT_ID = import.meta.env.VITE_VK_CLIENT_ID as string | undefined

function loginWithGoogle() {
  if (!GOOGLE_CLIENT_ID) return
  const redirectUri = `${window.location.origin}/auth/google/callback`
  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth')
  url.searchParams.set('client_id', GOOGLE_CLIENT_ID)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('scope', 'openid email profile')
  window.location.href = url.toString()
}

function loginWithVK() {
  if (!VK_CLIENT_ID) return
  const deviceId = crypto.randomUUID()
  const state = crypto.randomUUID()
  localStorage.setItem('vk_device_id', deviceId)
  localStorage.setItem('vk_state', state)
  const redirectUri = `${window.location.origin}/auth/vk/callback`
  const url = new URL('https://id.vk.com/authorize')
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('client_id', VK_CLIENT_ID)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('state', state)
  url.searchParams.set('device_id', deviceId)
  url.searchParams.set('scope', 'email')
  window.location.href = url.toString()
}

function TelegramLoginButton({
  botUsername,
  onAuth,
}: {
  botUsername: string
  onAuth: (user: Record<string, unknown>) => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !botUsername) return
    ;(window as Record<string, unknown>).__onTelegramAuth = onAuth
    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', botUsername)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-onauth', '__onTelegramAuth(user)')
    script.setAttribute('data-request-access', 'write')
    script.async = true
    ref.current.appendChild(script)
    return () => {
      delete (window as Record<string, unknown>).__onTelegramAuth
    }
  }, [botUsername, onAuth])

  return <div ref={ref} className="flex justify-center" />
}

type Mode = 'login' | 'register'

export default function LoginPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const { data: oauthConfig } = useQuery<OAuthConfigResponse>({
    queryKey: ['oauth-config'],
    queryFn: () => api.get<OAuthConfigResponse>('/api/auth/oauth-config'),
    staleTime: 5 * 60_000,
  })

  const showGoogle = oauthConfig?.google && !!GOOGLE_CLIENT_ID
  const showVK = oauthConfig?.vk && !!VK_CLIENT_ID
  const showTelegram = oauthConfig?.telegram && !!oauthConfig.telegram_bot_username
  const hasOAuth = showGoogle || showVK || showTelegram

  const handleTelegramAuth = useCallback(async (user: Record<string, unknown>) => {
    setError(null)
    setLoading(true)
    try {
      await api.post('/api/auth/oauth/telegram', user)
      navigate('/', { replace: true })
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Ошибка входа через Telegram')
    } finally {
      setLoading(false)
    }
  }, [navigate])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mode === 'login') {
        await api.post('/api/auth/login', { email, password })
      } else {
        await api.post('/api/auth/register', { email, password, display_name: displayName })
      }
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Ошибка сети')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-card bg-surface p-8 border border-border-neutral">
        <h1 className="text-xl font-bold text-text-primary mb-6">Вход в Skavellion</h1>

        {hasOAuth && (
          <div className="mb-5 flex flex-col gap-2">
            {showGoogle && (
              <button
                type="button"
                onClick={loginWithGoogle}
                className="w-full flex items-center justify-center gap-3 py-2 rounded-input border border-border-neutral bg-background text-sm text-text-primary hover:border-border-accent transition-colors"
              >
                <svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                  <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                  <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                  <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                  <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                  <path fill="none" d="M0 0h48v48H0z"/>
                </svg>
                Войти через Google
              </button>
            )}
            {showVK && (
              <button
                type="button"
                onClick={loginWithVK}
                className="w-full flex items-center justify-center gap-3 py-2 rounded-input border border-border-neutral bg-background text-sm text-text-primary hover:border-border-accent transition-colors"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.48 13.633c.34.332.698.649 1.004.999.135.155.263.316.36.497.138.258.015.544-.222.56l-1.469.002c-.38.031-.682-.12-.933-.375-.2-.205-.387-.425-.58-.637a1.21 1.21 0 00-.261-.228.472.472 0 00-.519.038.957.957 0 00-.228.36 1.948 1.948 0 01-.16.423c-.106.2-.3.256-.507.266-1.122.052-2.185-.123-3.167-.693-1.245-.728-2.173-1.762-2.974-2.927C7.554 9.853 7.019 8.648 6.509 7.432a.396.396 0 01.365-.547l1.476-.003c.218-.003.363.133.443.338.28.71.621 1.392 1.042 2.03.116.175.235.35.38.5.16.164.32.226.487.188.217-.05.337-.224.393-.432.036-.133.05-.269.056-.406.02-.456.025-.91-.067-1.363-.055-.274-.196-.451-.468-.503-.137-.027-.117-.1-.05-.177.11-.13.21-.213.416-.213h1.664c.276.005.367.143.404.42l.002 1.793c-.003.099.047.39.236.454.153.048.253-.068.345-.165.42-.452.717-1.005.986-1.572.118-.253.22-.514.318-.775.072-.193.187-.285.4-.282l1.608-.002c.048 0 .097.002.142.01.27.05.344.17.263.433a5.78 5.78 0 01-.306.742 12.94 12.94 0 01-.913 1.497c-.105.15-.22.292-.326.44-.09.127-.083.254.011.374.14.18.293.348.44.52l.866.965z" fill="#0077FF"/>
                </svg>
                Войти через ВКонтакте
              </button>
            )}
            {showTelegram && oauthConfig?.telegram_bot_username && (
              <TelegramLoginButton
                botUsername={oauthConfig.telegram_bot_username}
                onAuth={handleTelegramAuth}
              />
            )}
          </div>
        )}

        {hasOAuth && (
          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-border-neutral" />
            <span className="text-xs text-text-muted">или</span>
            <div className="flex-1 h-px bg-border-neutral" />
          </div>
        )}

        <div className="flex gap-2 mb-6">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(null) }}
            className={`flex-1 py-1.5 rounded-input text-sm font-medium transition-colors ${
              mode === 'login' ? 'bg-accent text-background' : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Войти
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(null) }}
            className={`flex-1 py-1.5 rounded-input text-sm font-medium transition-colors ${
              mode === 'register' ? 'bg-accent text-background' : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Регистрация
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'register' && (
            <div>
              <label className="block text-sm text-text-secondary mb-1">Имя</label>
              <input
                type="text"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                required
                className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
                placeholder="Ваше имя"
              />
            </div>
          )}
          <div>
            <label className="block text-sm text-text-secondary mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Пароль</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
              placeholder="Минимум 8 символов"
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 rounded-input bg-accent text-background font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {loading ? 'Загрузка...' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </button>
        </form>
      </div>
    </div>
  )
}

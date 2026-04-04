import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '@/lib/api'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

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

type Mode = 'login' | 'register'

export default function LoginPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

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

        {GOOGLE_CLIENT_ID && (
          <div className="mb-5">
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
          </div>
        )}

        {GOOGLE_CLIENT_ID && (
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
              mode === 'login'
                ? 'bg-accent text-background'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Войти
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(null) }}
            className={`flex-1 py-1.5 rounded-input text-sm font-medium transition-colors ${
              mode === 'register'
                ? 'bg-accent text-background'
                : 'text-text-secondary hover:text-text-primary'
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

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

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

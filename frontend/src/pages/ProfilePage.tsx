import { useState, useEffect, useRef } from 'react'
import { useQueryClient, useMutation, useQuery } from '@tanstack/react-query'
import { User, Trash2, Clock, Loader2, CheckCircle, XCircle, AlertCircle, Plus } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useTransactions } from '@/hooks/useTransactions'
import { api, ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { OAuthConfigResponse } from '@/types/api'

const PROVIDER_LABELS: Record<string, string> = {
  telegram: 'Telegram',
  google: 'Google',
  vk: 'VK',
  email: 'Email',
}

const PROVIDER_COLORS: Record<string, string> = {
  telegram: 'text-[#229ED9]',
  google: 'text-[#EA4335]',
  vk: 'text-[#0077FF]',
  email: 'text-text-muted',
}

const TX_TYPE_LABELS: Record<string, string> = {
  trial_activation: 'Пробный период',
  payment: 'Оплата',
  promo_bonus: 'Промокод',
  manual: 'Вручную',
}

function TxStatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle size={14} className="text-emerald-400 shrink-0" />
  if (status === 'failed') return <XCircle size={14} className="text-red-400 shrink-0" />
  return <Clock size={14} className="text-yellow-400 shrink-0 animate-pulse" />
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined
const VK_CLIENT_ID = import.meta.env.VITE_VK_CLIENT_ID as string | undefined

function startGoogleLink() {
  if (!GOOGLE_CLIENT_ID) return
  localStorage.setItem('oauth_intent', 'link')
  const redirectUri = `${window.location.origin}/auth/google/callback`
  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth')
  url.searchParams.set('client_id', GOOGLE_CLIENT_ID)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('scope', 'openid email profile')
  window.location.href = url.toString()
}

function startVKLink() {
  if (!VK_CLIENT_ID) return
  const deviceId = crypto.randomUUID()
  const state = crypto.randomUUID()
  localStorage.setItem('vk_device_id', deviceId)
  localStorage.setItem('vk_state', state)
  localStorage.setItem('oauth_intent', 'link')
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

export default function ProfilePage() {
  const queryClient = useQueryClient()
  const { user, isLoading: authLoading } = useAuth()
  const { data: transactions = [], isLoading: txLoading } = useTransactions()

  const unlinkMutation = useMutation({
    mutationFn: (provider: string) =>
      api.delete(`/api/users/me/providers/${provider}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })

  const { data: oauthConfig } = useQuery<OAuthConfigResponse>({
    queryKey: ['oauth-config'],
    queryFn: () => api.get<OAuthConfigResponse>('/api/auth/oauth-config'),
    staleTime: 5 * 60_000,
  })

  const [showEmailForm, setShowEmailForm] = useState(false)
  const [linkEmail, setLinkEmail] = useState('')
  const [linkPassword, setLinkPassword] = useState('')
  const [linkEmailError, setLinkEmailError] = useState<string | null>(null)
  const [linkTelegramError, setLinkTelegramError] = useState<string | null>(null)

  const linkEmailMutation = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.post('/api/users/me/providers/email', { email, password }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
      setShowEmailForm(false)
      setLinkEmail('')
      setLinkPassword('')
      setLinkEmailError(null)
    },
    onError: (e) => setLinkEmailError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  const telegramLinkRef = useRef<HTMLDivElement>(null)

  const linkedTypes = new Set(user?.providers.map((p) => p.type) ?? [])

  const canAddGoogle = oauthConfig?.google && !!GOOGLE_CLIENT_ID && !linkedTypes.has('google')
  const canAddVK = oauthConfig?.vk && !!VK_CLIENT_ID && !linkedTypes.has('vk')
  const canAddTelegram = oauthConfig?.telegram && !!oauthConfig.telegram_bot_username && !linkedTypes.has('telegram')
  const canAddEmail = !linkedTypes.has('email')
  const hasAddable = canAddGoogle || canAddVK || canAddTelegram || canAddEmail

  useEffect(() => {
    if (!canAddTelegram || !oauthConfig?.telegram_bot_username || !telegramLinkRef.current) return
    ;(window as unknown as Record<string, unknown>).__onTelegramLink = async (tgUser: Record<string, unknown>) => {
      try {
        await api.post('/api/users/me/providers/telegram', tgUser)
        queryClient.invalidateQueries({ queryKey: ['me'] })
        setLinkTelegramError(null)
      } catch (e) {
        setLinkTelegramError(e instanceof ApiError ? e.detail : 'Ошибка Telegram')
      }
    }
    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', oauthConfig.telegram_bot_username)
    script.setAttribute('data-size', 'medium')
    script.setAttribute('data-onauth', '__onTelegramLink(user)')
    script.setAttribute('data-request-access', 'write')
    script.async = true
    telegramLinkRef.current.appendChild(script)
    return () => { delete (window as unknown as Record<string, unknown>).__onTelegramLink }
  }, [canAddTelegram, oauthConfig?.telegram_bot_username])

  if (authLoading) {
    return (
      <div className="p-6 flex justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  if (!user) return null

  const shortId = user.id.slice(0, 8).toUpperCase()
  const canUnlink = user.providers.length > 1

  return (
    <div className="p-4 md:p-6 max-w-xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Профиль</h1>

      {/* Account info */}
      <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
        <div className="flex items-center gap-4 mb-4">
          <div className="h-12 w-12 rounded-full bg-accent/20 flex items-center justify-center text-lg font-bold text-accent shrink-0">
            {user.display_name[0].toUpperCase()}
          </div>
          <div>
            <p className="font-semibold text-text-primary">{user.display_name}</p>
            <p className="text-xs text-text-muted">#{shortId}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-text-muted text-xs mb-0.5">Аккаунт создан</p>
            <p className="text-text-secondary">{formatDate(user.created_at)}</p>
          </div>
          <div>
            <p className="text-text-muted text-xs mb-0.5">Роль</p>
            <p className="text-text-secondary">{user.is_admin ? 'Администратор' : 'Пользователь'}</p>
          </div>
        </div>
      </div>

      {/* Linked providers */}
      <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
        <h2 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
          <User size={14} className="text-accent" /> Привязанные аккаунты
        </h2>
        {user.providers.length === 0 ? (
          <p className="text-xs text-text-muted">Нет привязанных аккаунтов</p>
        ) : (
          <div className="space-y-2">
            {user.providers.map((p) => (
              <div
                key={p.type}
                className="flex items-center justify-between rounded-input bg-white/5 px-3 py-2.5"
              >
                <div className="flex items-center gap-2.5">
                  <span className={cn('text-sm font-medium', PROVIDER_COLORS[p.type] ?? 'text-text-secondary')}>
                    {PROVIDER_LABELS[p.type] ?? p.type}
                  </span>
                  {p.username && (
                    <span className="text-xs text-text-muted">@{p.username}</span>
                  )}
                </div>
                {canUnlink && (
                  <button
                    onClick={() => unlinkMutation.mutate(p.type)}
                    disabled={unlinkMutation.isPending}
                    className="text-text-muted hover:text-red-400 transition-colors disabled:opacity-50"
                    title="Отвязать"
                  >
                    {unlinkMutation.isPending ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Trash2 size={14} />
                    )}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {!canUnlink && (
          <p className="mt-2 text-xs text-text-muted flex items-center gap-1.5">
            <AlertCircle size={12} />
            Нельзя отвязать единственный способ входа
          </p>
        )}
        {unlinkMutation.isError && (
          <p className="mt-2 text-xs text-red-400">
            {unlinkMutation.error instanceof ApiError ? unlinkMutation.error.detail : 'Ошибка'}
          </p>
        )}
      </div>

      {/* Add auth method */}
      {hasAddable && (
        <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
          <h2 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
            <Plus size={14} className="text-accent" /> Добавить способ входа
          </h2>
          <div className="flex flex-col gap-2">
            {canAddGoogle && (
              <button
                onClick={startGoogleLink}
                className="flex items-center gap-2.5 rounded-input bg-white/5 px-3 py-2.5 text-sm text-text-secondary hover:text-text-primary transition-colors text-left"
              >
                Google
              </button>
            )}
            {canAddVK && (
              <button
                onClick={startVKLink}
                className="flex items-center gap-2.5 rounded-input bg-white/5 px-3 py-2.5 text-sm text-text-secondary hover:text-text-primary transition-colors text-left"
              >
                ВКонтакте
              </button>
            )}
            {canAddTelegram && (
              <div>
                <div ref={telegramLinkRef} />
                {linkTelegramError && <p className="mt-1 text-xs text-red-400">{linkTelegramError}</p>}
              </div>
            )}
            {canAddEmail && !showEmailForm && (
              <button
                onClick={() => setShowEmailForm(true)}
                className="flex items-center gap-2.5 rounded-input bg-white/5 px-3 py-2.5 text-sm text-text-secondary hover:text-text-primary transition-colors text-left"
              >
                Email
              </button>
            )}
            {canAddEmail && showEmailForm && (
              <div className="space-y-2">
                <input
                  type="email"
                  value={linkEmail}
                  onChange={e => setLinkEmail(e.target.value)}
                  placeholder="Email"
                  className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
                />
                <input
                  type="password"
                  value={linkPassword}
                  onChange={e => setLinkPassword(e.target.value)}
                  placeholder="Пароль (мин. 8 символов)"
                  minLength={8}
                  className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
                />
                {linkEmailError && <p className="text-xs text-red-400">{linkEmailError}</p>}
                <div className="flex gap-2">
                  <button
                    onClick={() => linkEmailMutation.mutate({ email: linkEmail, password: linkPassword })}
                    disabled={linkEmailMutation.isPending || !linkEmail || !linkPassword}
                    className="flex-1 py-1.5 rounded-input bg-accent text-background text-xs font-medium disabled:opacity-50"
                  >
                    {linkEmailMutation.isPending ? 'Сохранение…' : 'Добавить Email'}
                  </button>
                  <button
                    onClick={() => { setShowEmailForm(false); setLinkEmailError(null) }}
                    className="px-3 py-1.5 rounded-input bg-white/5 text-text-secondary text-xs"
                  >
                    Отмена
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Transaction history */}
      <div className="rounded-card bg-surface border border-border-neutral p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-3">История операций</h2>
        {txLoading ? (
          <div className="flex justify-center py-4">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        ) : transactions.length === 0 ? (
          <p className="text-xs text-text-muted text-center py-4">Нет операций</p>
        ) : (
          <div className="space-y-2">
            {transactions.map((tx) => (
              <div
                key={tx.id}
                className="flex items-center gap-3 rounded-input bg-white/5 px-3 py-2.5"
              >
                <TxStatusIcon status={tx.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-text-primary truncate">
                    {TX_TYPE_LABELS[tx.type] ?? tx.type}
                    {tx.plan_name ? ` · ${tx.plan_name}` : ''}
                  </p>
                  <p className="text-[10px] text-text-muted">{formatDate(tx.created_at)}</p>
                </div>
                <div className="text-right shrink-0">
                  {tx.amount_rub != null && tx.amount_rub > 0 && (
                    <p className="text-xs text-text-primary">{tx.amount_rub}₽</p>
                  )}
                  {tx.days_added != null && (
                    <p className="text-[10px] text-emerald-400">+{tx.days_added} дн.</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

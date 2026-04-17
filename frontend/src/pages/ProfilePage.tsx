import { useState, useEffect, useRef } from 'react'
import { useQueryClient, useMutation, useQuery } from '@tanstack/react-query'
import { User, Trash2, Clock, Loader2, CheckCircle, XCircle, AlertCircle, Plus, Pencil, Check, X, KeyRound } from 'lucide-react'
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

function isStrongPassword(p: string) {
  return p.length >= 8 && /[A-Z]/.test(p) && /[a-z]/.test(p) && /[0-9]/.test(p)
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

function startGoogleLink(clientId: string) {
  localStorage.setItem('oauth_intent', 'link')
  const redirectUri = `${window.location.origin}/auth/google/callback`
  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth')
  url.searchParams.set('client_id', clientId)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('scope', 'openid email profile')
  window.location.href = url.toString()
}

function startVKLink(clientId: string) {
  const deviceId = crypto.randomUUID()
  const state = crypto.randomUUID()
  localStorage.setItem('vk_device_id', deviceId)
  localStorage.setItem('vk_state', state)
  localStorage.setItem('oauth_intent', 'link')
  const redirectUri = `${window.location.origin}/auth/vk/callback`
  const url = new URL('https://id.vk.com/authorize')
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('client_id', clientId)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('state', state)
  url.searchParams.set('device_id', deviceId)
  url.searchParams.set('scope', 'email')
  window.location.href = url.toString()
}

function TelegramLinkButton({
  botUsername,
  onAuth,
}: {
  botUsername: string
  onAuth: (user: Record<string, unknown>) => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !botUsername) return
    ;(window as unknown as Record<string, unknown>).__onTelegramLink = onAuth

    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', botUsername)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-onauth', '__onTelegramLink(user)')
    script.setAttribute('data-request-access', 'write')
    script.async = true
    ref.current.appendChild(script)

    const observer = new MutationObserver(() => {
      const iframe = ref.current?.querySelector('iframe')
      if (!iframe) return
      observer.disconnect()
      const applyScale = () => {
        const containerWidth = ref.current?.offsetWidth
        const iframeWidth = iframe.offsetWidth
        if (!containerWidth || !iframeWidth) { requestAnimationFrame(applyScale); return }
        iframe.style.opacity = '0'
        iframe.style.position = 'absolute'
        iframe.style.top = '0'
        iframe.style.left = '0'
        iframe.style.transformOrigin = 'left top'
        iframe.style.transform = `scaleX(${containerWidth / iframeWidth})`
        iframe.style.cursor = 'pointer'
      }
      applyScale()
    })
    observer.observe(ref.current, { childList: true, subtree: true })

    return () => {
      observer.disconnect()
      delete (window as unknown as Record<string, unknown>).__onTelegramLink
    }
  }, [botUsername, onAuth])

  return (
    <div className="group relative h-[42px]">
      <div className="absolute inset-0 flex items-center gap-2.5 rounded-input bg-white/5 px-3 text-sm text-text-secondary group-hover:text-text-primary pointer-events-none select-none transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
          <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M8.287 5.906q-1.168.486-4.666 2.01-.567.225-.595.442c-.03.243.275.339.69.47l.175.055c.408.133.958.288 1.243.294q.39.01.868-.32 3.269-2.206 3.374-2.23c.05-.012.12-.026.166.016s.042.12.037.141c-.03.129-1.227 1.241-1.846 1.817-.193.18-.33.307-.358.336a8 8 0 0 1-.188.186c-.38.366-.664.64.015 1.088.327.216.589.393.85.571.284.194.568.387.936.629q.14.092.27.187c.331.236.63.448.997.414.214-.02.435-.22.547-.82.265-1.417.786-4.486.906-5.751a1.4 1.4 0 0 0-.013-.315.34.34 0 0 0-.114-.217.53.53 0 0 0-.31-.093c-.3.005-.763.166-2.984 1.09" fill="#2AABEE"/>
        </svg>
        Telegram
      </div>
      <div ref={ref} className="absolute inset-0 overflow-hidden" />
    </div>
  )
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

  const [isEditingName, setIsEditingName] = useState(false)
  const [nameInput, setNameInput] = useState('')
  const [nameError, setNameError] = useState<string | null>(null)

  const updateNameMutation = useMutation({
    mutationFn: (display_name: string) => api.patch('/api/users/me', { display_name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
      setIsEditingName(false)
      setNameError(null)
    },
    onError: (e) => setNameError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  const [showEmailForm, setShowEmailForm] = useState(false)
  const [linkEmail, setLinkEmail] = useState('')
  const [linkPassword, setLinkPassword] = useState('')
  const [linkEmailError, setLinkEmailError] = useState<string | null>(null)
  const [linkTelegramError, setLinkTelegramError] = useState<string | null>(null)
  const [linkTelegramNotification, setLinkTelegramNotification] = useState<string | null>(null)

  const [changePasswordOpen, setChangePasswordOpen] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmNewPassword, setConfirmNewPassword] = useState('')
  const [changePasswordError, setChangePasswordError] = useState<string | null>(null)

  const changePasswordMutation = useMutation({
    mutationFn: ({ old_password, new_password }: { old_password: string; new_password: string }) =>
      api.patch('/api/users/me/password', { old_password, new_password }),
    onSuccess: () => {
      setChangePasswordOpen(false)
      setOldPassword('')
      setNewPassword('')
      setConfirmNewPassword('')
      setChangePasswordError(null)
    },
    onError: (e) => setChangePasswordError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

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

  const linkedTypes = new Set(user?.providers.map((p) => p.type) ?? [])

  const canAddGoogle = oauthConfig?.google && !!oauthConfig.google_client_id && !linkedTypes.has('google')
  const canAddVK = oauthConfig?.vk && !!oauthConfig.vk_client_id && !linkedTypes.has('vk')
  const canAddTelegram = oauthConfig?.telegram && !!oauthConfig.telegram_bot_username && !linkedTypes.has('telegram')
  const canAddEmail = (oauthConfig?.email_enabled !== false) && !linkedTypes.has('email')
  const hasAddable = canAddGoogle || canAddVK || canAddTelegram || canAddEmail

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
            {isEditingName ? (
              <div className="flex items-center gap-1.5">
                <input
                  type="text"
                  value={nameInput}
                  onChange={e => setNameInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      const trimmed = nameInput.trim()
                      if (!trimmed) { setNameError('Имя не может быть пустым'); return }
                      if (trimmed.length > 64) { setNameError('Не более 64 символов'); return }
                      updateNameMutation.mutate(trimmed)
                    }
                    if (e.key === 'Escape') { setIsEditingName(false); setNameError(null) }
                  }}
                  autoFocus
                  maxLength={64}
                  className="bg-background border border-border-neutral rounded-input px-2 py-0.5 text-sm text-text-primary focus:outline-none focus:border-accent font-semibold"
                />
                <button
                  onClick={() => {
                    const trimmed = nameInput.trim()
                    if (!trimmed) { setNameError('Имя не может быть пустым'); return }
                    if (trimmed.length > 64) { setNameError('Не более 64 символов'); return }
                    updateNameMutation.mutate(trimmed)
                  }}
                  disabled={updateNameMutation.isPending}
                  className="text-accent hover:text-accent/80 transition-colors disabled:opacity-50"
                >
                  {updateNameMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                </button>
                <button
                  onClick={() => { setIsEditingName(false); setNameError(null) }}
                  className="text-text-muted hover:text-text-primary transition-colors"
                >
                  <X size={14} />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-1.5">
                <p className="font-semibold text-text-primary">{user.display_name}</p>
                <button
                  onClick={() => { setNameInput(user.display_name); setIsEditingName(true); setNameError(null) }}
                  className="text-text-muted hover:text-text-primary transition-colors"
                >
                  <Pencil size={13} />
                </button>
              </div>
            )}
            {nameError && <p className="text-xs text-red-400 mt-0.5">{nameError}</p>}
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
              <div key={p.type}>
                <div
                  className="flex items-center justify-between rounded-input bg-white/5 px-3 py-2.5"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className={cn('text-sm font-medium shrink-0', PROVIDER_COLORS[p.type] ?? 'text-text-secondary')}>
                      {PROVIDER_LABELS[p.type] ?? p.type}
                    </span>
                    {p.identifier && (
                      <span className="text-xs text-text-muted truncate">{p.identifier}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {p.type === 'email' && (
                      <button
                        onClick={() => { setChangePasswordOpen(v => !v); setChangePasswordError(null) }}
                        className="text-text-muted hover:text-accent transition-colors"
                        title="Изменить пароль"
                      >
                        <KeyRound size={14} />
                      </button>
                    )}
                    {canUnlink && (
                      <button
                        onClick={() => unlinkMutation.mutate(p.type)}
                        disabled={unlinkMutation.isPending}
                        className="text-text-muted hover:text-red-400 transition-colors disabled:opacity-50"
                        title="Отвязать"
                      >
                        {unlinkMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      </button>
                    )}
                  </div>
                </div>
                {p.type === 'email' && changePasswordOpen && (
                  <div className="mt-2 space-y-2">
                    <input
                      type="password"
                      value={oldPassword}
                      onChange={e => setOldPassword(e.target.value)}
                      placeholder="Текущий пароль"
                      className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
                    />
                    <input
                      type="password"
                      value={newPassword}
                      onChange={e => setNewPassword(e.target.value)}
                      placeholder="Новый пароль"
                      className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
                    />
                    {newPassword && !isStrongPassword(newPassword) && (
                      <p className="text-xs text-text-muted">Мин. 8 символов, заглавная, строчная, цифра</p>
                    )}
                    <input
                      type="password"
                      value={confirmNewPassword}
                      onChange={e => setConfirmNewPassword(e.target.value)}
                      placeholder="Повторите новый пароль"
                      className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
                    />
                    {confirmNewPassword && newPassword !== confirmNewPassword && (
                      <p className="text-xs text-red-400">Пароли не совпадают</p>
                    )}
                    {changePasswordError && <p className="text-xs text-red-400">{changePasswordError}</p>}
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          if (!isStrongPassword(newPassword)) {
                            setChangePasswordError('Пароль должен содержать не менее 8 символов, заглавную букву, строчную букву и цифру')
                            return
                          }
                          if (newPassword !== confirmNewPassword) {
                            setChangePasswordError('Пароли не совпадают')
                            return
                          }
                          changePasswordMutation.mutate({ old_password: oldPassword, new_password: newPassword })
                        }}
                        disabled={changePasswordMutation.isPending || !oldPassword || !newPassword || !confirmNewPassword}
                        className="flex-1 py-1.5 rounded-input bg-accent text-background text-xs font-medium disabled:opacity-50"
                      >
                        {changePasswordMutation.isPending ? 'Сохранение…' : 'Сохранить'}
                      </button>
                      <button
                        onClick={() => { setChangePasswordOpen(false); setChangePasswordError(null); setOldPassword(''); setNewPassword(''); setConfirmNewPassword('') }}
                        className="px-3 py-1.5 rounded-input bg-white/5 text-text-secondary text-xs"
                      >
                        Отмена
                      </button>
                    </div>
                  </div>
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
            {canAddGoogle && oauthConfig?.google_client_id && (
              <button
                onClick={() => startGoogleLink(oauthConfig.google_client_id!)}
                className="flex items-center gap-2.5 rounded-input bg-white/5 px-3 py-2.5 text-sm text-text-secondary hover:text-text-primary transition-colors text-left"
              >
                Google
              </button>
            )}
            {canAddVK && oauthConfig?.vk_client_id && (
              <button
                onClick={() => startVKLink(oauthConfig.vk_client_id!)}
                className="flex items-center gap-2.5 rounded-input bg-white/5 px-3 py-2.5 text-sm text-text-secondary hover:text-text-primary transition-colors text-left"
              >
                ВКонтакте
              </button>
            )}
            {canAddTelegram && oauthConfig?.telegram_bot_username && (
              <div>
                <TelegramLinkButton
                  botUsername={oauthConfig.telegram_bot_username}
                  onAuth={async (tgUser) => {
                    try {
                      const res = await api.post<{ ok: boolean; notification?: string | null }>(
                        '/api/users/me/providers/telegram',
                        tgUser,
                      )
                      queryClient.invalidateQueries({ queryKey: ['me'] })
                      setLinkTelegramError(null)
                      setLinkTelegramNotification(res.notification ?? null)
                    } catch (e) {
                      setLinkTelegramError(e instanceof ApiError ? e.detail : 'Ошибка Telegram')
                    }
                  }}
                />
                {linkTelegramError && <p className="mt-1 text-xs text-red-400">{linkTelegramError}</p>}
                {linkTelegramNotification && (
                  <div className="mt-2 flex items-start gap-2 rounded-input bg-amber-500/10 border border-amber-500/20 px-3 py-2">
                    <AlertCircle size={14} className="text-amber-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-200 leading-relaxed">{linkTelegramNotification}</p>
                  </div>
                )}
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

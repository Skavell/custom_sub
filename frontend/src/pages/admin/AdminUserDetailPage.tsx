import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, RefreshCw, Shield, ShieldOff, UserCheck, UserX,
  RotateCcw, CheckCircle, XCircle, AlertTriangle,
} from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import type { UserAdminDetail, SetRemnawaveUuidRequest } from '@/types/api'

// ─── Confirmation dialog ──────────────────────────────────────────────────────

interface ConfirmDialogProps {
  message: string
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDialog({ message, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
      <div className="bg-surface border border-border-neutral rounded-card p-6 max-w-sm w-full space-y-4">
        <p className="text-sm text-text-primary">{message}</p>
        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            className="flex-1 py-2 rounded-input bg-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/30 transition-colors"
          >
            Подтвердить
          </button>
          <button
            onClick={onCancel}
            className="flex-1 py-2 rounded-input bg-surface border border-border-neutral text-text-secondary text-sm hover:border-accent transition-colors"
          >
            Отмена
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Info row ────────────────────────────────────────────────────────────────

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4 py-2 border-b border-border-neutral/50 last:border-0">
      <span className="text-xs text-text-muted sm:w-36 shrink-0">{label}</span>
      <span className="text-sm text-text-primary break-all">{value ?? '—'}</span>
    </div>
  )
}

// ─── Action button ───────────────────────────────────────────────────────────

function ActionBtn({
  onClick, icon, label, variant = 'default', disabled,
}: {
  onClick: () => void
  icon: React.ReactNode
  label: string
  variant?: 'default' | 'danger'
  disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-2 px-3 py-2 rounded-input text-xs font-medium transition-colors disabled:opacity-50 ${
        variant === 'danger'
          ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20'
          : 'bg-surface border border-border-neutral text-text-secondary hover:border-accent hover:text-accent'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user: currentAdmin } = useAuth()

  const [uuidInput, setUuidInput] = useState('')
  const [confirm, setConfirm] = useState<{ message: string; action: () => void } | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [errMsg, setErrMsg] = useState<string | null>(null)

  const flash = (text: string) => {
    setMsg(text)
    setTimeout(() => setMsg(null), 3000)
  }
  const flashErr = (text: string) => {
    setErrMsg(text)
    setTimeout(() => setErrMsg(null), 4000)
  }

  const { data: user, isLoading, error } = useQuery<UserAdminDetail>({
    queryKey: ['admin-user', id],
    queryFn: () => api.get<UserAdminDetail>(`/api/admin/users/${id}`),
    enabled: !!id,
  })

  useEffect(() => {
    if (user) setUuidInput(user.remnawave_uuid ?? '')
  }, [user])

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin-user', id] })

  const banMutation = useMutation({
    mutationFn: () => api.patch<UserAdminDetail>(`/api/admin/users/${id}/ban`, {}),
    onSuccess: (updated: UserAdminDetail) => {
      queryClient.setQueryData(['admin-user', id], updated)
      flash(updated.is_banned ? 'Пользователь заблокирован' : 'Пользователь разблокирован')
    },
  })

  const adminMutation = useMutation({
    mutationFn: () => api.patch<UserAdminDetail>(`/api/admin/users/${id}/admin`, {}),
    onSuccess: (updated: UserAdminDetail) => {
      queryClient.setQueryData(['admin-user', id], updated)
      flash(updated.is_admin ? 'Права администратора выданы' : 'Права администратора отозваны')
    },
  })

  const resetSubMutation = useMutation({
    mutationFn: () => api.post(`/api/admin/users/${id}/reset-subscription`, {}),
    onSuccess: () => {
      invalidate()
      flash('Подписка сброшена')
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => api.post(`/api/admin/users/${id}/sync`, {}),
    onSuccess: () => { invalidate(); flash('Синхронизация выполнена') },
  })

  const setUuidMutation = useMutation({
    mutationFn: (data: SetRemnawaveUuidRequest) =>
      api.patch(`/api/admin/users/${id}/remnawave-uuid`, data),
    onSuccess: () => {
      invalidate()
      flash('UUID обновлён и синхронизирован')
    },
    onError: (err) => {
      flashErr(err instanceof ApiError ? err.detail : 'Ошибка')
    },
  })

  const askConfirm = (message: string, action: () => void) =>
    setConfirm({ message, action })

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  if (error || !user) {
    return (
      <div className="p-6">
        <p className="text-xs text-red-400">
          {error instanceof ApiError ? error.detail : 'Пользователь не найден'}
        </p>
      </div>
    )
  }

  const isSelf = currentAdmin?.id === user.id
  const sub = user.subscription

  return (
    <div className="max-w-2xl mx-auto space-y-6 p-4 sm:p-6">
      {confirm && (
        <ConfirmDialog
          message={confirm.message}
          onConfirm={() => { confirm.action(); setConfirm(null) }}
          onCancel={() => setConfirm(null)}
        />
      )}

      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/admin/users')}
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-semibold text-text-primary truncate">{user.display_name}</h1>
        {user.is_banned && (
          <span className="px-2 py-0.5 rounded text-xs bg-red-500/15 text-red-400">Заблокирован</span>
        )}
        {user.is_admin && (
          <span className="px-2 py-0.5 rounded text-xs bg-accent/15 text-accent">Админ</span>
        )}
      </div>

      {msg && (
        <div className="flex items-center gap-2 text-xs text-green-400 bg-green-500/10 rounded-input px-3 py-2">
          <CheckCircle size={13} />
          {msg}
        </div>
      )}
      {errMsg && (
        <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 rounded-input px-3 py-2">
          <XCircle size={13} />
          {errMsg}
        </div>
      )}

      {/* Info section */}
      <div className="rounded-card bg-surface border border-border-neutral p-4 sm:p-5 space-y-0.5">
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">
          Информация
        </h2>
        <InfoRow label="ID" value={<span className="font-mono text-xs">{user.id}</span>} />
        <InfoRow
          label="Email"
          value={
            user.email ? (
              <span className="flex items-center gap-2">
                {user.email}
                {user.email_verified === true && (
                  <CheckCircle size={13} className="text-green-400 shrink-0" />
                )}
                {user.email_verified === false && (
                  <XCircle size={13} className="text-yellow-400 shrink-0" />
                )}
              </span>
            ) : null
          }
        />
        <InfoRow
          label="Провайдеры"
          value={
            <div className="space-y-1">
              {user.providers.map((p) => (
                <div key={p.provider} className="flex items-center gap-2 text-xs">
                  <span className="font-medium text-text-primary capitalize">{p.provider}</span>
                  {p.provider_username && (
                    <span className="text-text-muted">@{p.provider_username}</span>
                  )}
                  {p.provider_user_id && (
                    <span className="font-mono text-text-muted">{p.provider_user_id}</span>
                  )}
                </div>
              ))}
            </div>
          }
        />
        <InfoRow label="Создан" value={new Date(user.created_at).toLocaleString('ru-RU')} />
        <InfoRow label="Последний вход" value={new Date(user.last_seen_at).toLocaleString('ru-RU')} />
        <InfoRow
          label="Подписка"
          value={
            sub ? (
              <span>
                {sub.type} · {sub.status} · до {new Date(sub.expires_at).toLocaleDateString('ru-RU')}
                {sub.traffic_limit_gb != null && ` · ${sub.traffic_limit_gb} ГБ`}
              </span>
            ) : null
          }
        />
        <InfoRow
          label="Remnawave UUID"
          value={
            user.remnawave_uuid ? (
              <span className="font-mono text-xs">{user.remnawave_uuid}</span>
            ) : null
          }
        />
      </div>

      {/* Actions */}
      <div className="rounded-card bg-surface border border-border-neutral p-4 sm:p-5 space-y-4">
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-wider">
          Действия
        </h2>

        <div className="flex flex-wrap gap-2">
          {/* Ban */}
          <ActionBtn
            onClick={() =>
              askConfirm(
                user.is_banned
                  ? `Разблокировать пользователя ${user.display_name}?`
                  : `Заблокировать пользователя ${user.display_name}?`,
                () => banMutation.mutate(),
              )
            }
            icon={user.is_banned ? <Shield size={14} /> : <ShieldOff size={14} />}
            label={user.is_banned ? 'Разблокировать' : 'Заблокировать'}
            variant={user.is_banned ? 'default' : 'danger'}
            disabled={isSelf || banMutation.isPending}
          />

          {/* Admin toggle */}
          <ActionBtn
            onClick={() =>
              askConfirm(
                user.is_admin
                  ? `Забрать права администратора у ${user.display_name}?`
                  : `Выдать права администратора ${user.display_name}?`,
                () => adminMutation.mutate(),
              )
            }
            icon={user.is_admin ? <UserX size={14} /> : <UserCheck size={14} />}
            label={user.is_admin ? 'Забрать права' : 'Сделать админом'}
            disabled={isSelf || adminMutation.isPending}
          />

          {/* Reset subscription */}
          <ActionBtn
            onClick={() =>
              askConfirm(
                `Сбросить подписку пользователя ${user.display_name}? Локальный сброс — Remnawave не затронут.`,
                () => resetSubMutation.mutate(),
              )
            }
            icon={<RotateCcw size={14} />}
            label="Сбросить подписку"
            variant="danger"
            disabled={!sub || resetSubMutation.isPending}
          />

          {/* Sync */}
          <ActionBtn
            onClick={() =>
              askConfirm(
                `Синхронизировать ${user.display_name} с Remnawave?`,
                () => syncMutation.mutate(),
              )
            }
            icon={<RefreshCw size={14} />}
            label="Синхронизировать"
            disabled={!user.remnawave_uuid || syncMutation.isPending}
          />
        </div>

        {/* Remnawave UUID */}
        <div className="space-y-2 pt-2 border-t border-border-neutral/50">
          <p className="text-xs text-text-muted">Remnawave UUID</p>
          {user.subscription_conflict && (
            <div className="flex items-center gap-2 text-xs text-yellow-400">
              <AlertTriangle size={13} />
              Конфликт UUID — укажите правильный UUID:
            </div>
          )}
          <div className="flex gap-2">
            <input
              value={uuidInput}
              onChange={(e) => setUuidInput(e.target.value)}
              placeholder="UUID из Remnawave"
              className="flex-1 rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent font-mono"
            />
            <button
              onClick={() => setUuidMutation.mutate({ remnawave_uuid: uuidInput.trim() })}
              disabled={!uuidInput.trim() || setUuidMutation.isPending}
              className="px-3 py-1.5 rounded-input bg-accent/10 text-accent text-xs font-medium hover:bg-accent/20 transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              {setUuidMutation.isPending ? 'Применение...' : 'Применить и синхронизировать'}
            </button>
          </div>
        </div>
      </div>

      {/* Recent transactions */}
      {user.recent_transactions.length > 0 && (
        <div className="rounded-card bg-surface border border-border-neutral p-4 sm:p-5 space-y-3">
          <h2 className="text-xs font-medium text-text-muted uppercase tracking-wider">
            Последние транзакции
          </h2>
          <div className="space-y-2">
            {user.recent_transactions.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between text-xs">
                <span className="text-text-secondary">{tx.type}</span>
                <span className="text-text-muted">{new Date(tx.created_at).toLocaleDateString('ru-RU')}</span>
                <span className={tx.status === 'completed' ? 'text-green-400' : 'text-text-muted'}>
                  {tx.status}
                </span>
                {tx.days_added != null && (
                  <span className="text-accent">+{tx.days_added}д</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

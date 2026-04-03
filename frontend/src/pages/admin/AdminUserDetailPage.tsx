// frontend/src/pages/admin/AdminUserDetailPage.tsx
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { UserAdminDetail, ConflictResolveRequest } from '@/types/api'

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [syncMsg, setSyncMsg] = useState<string | null>(null)
  const [resolveMsg, setResolveMsg] = useState<string | null>(null)
  const [resolveUuid, setResolveUuid] = useState('')

  const { data: user, isLoading, error } = useQuery<UserAdminDetail>({
    queryKey: ['admin-user', id],
    queryFn: () => api.get<UserAdminDetail>(`/api/admin/users/${id}`),
    enabled: !!id,
  })

  const syncMutation = useMutation({
    mutationFn: () => api.post(`/api/admin/users/${id}/sync`, {}),
    onSuccess: () => {
      setSyncMsg('Синхронизация выполнена')
      queryClient.invalidateQueries({ queryKey: ['admin-user', id] })
      setTimeout(() => setSyncMsg(null), 3000)
    },
  })

  const resolveMutation = useMutation({
    mutationFn: (data: ConflictResolveRequest) =>
      api.post(`/api/admin/users/${id}/resolve-conflict`, data),
    onSuccess: () => {
      setResolveMsg('Конфликт разрешён')
      queryClient.invalidateQueries({ queryKey: ['admin-user', id] })
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setTimeout(() => setResolveMsg(null), 3000)
    },
  })

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

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <button
        onClick={() => navigate('/admin/users')}
        className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary mb-5 transition-colors"
      >
        <ArrowLeft size={15} /> Назад
      </button>

      <div className="flex items-start justify-between mb-5 gap-3">
        <div>
          <h1 className="text-xl font-bold text-text-primary">{user.display_name}</h1>
          <p className="text-xs text-text-muted mt-0.5">
            {user.providers.map((p) => p.provider_username ?? p.provider).join(' · ')}
          </p>
        </div>
        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-white/5 text-sm text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors"
        >
          <RefreshCw size={14} className={syncMutation.isPending ? 'animate-spin' : ''} />
          Синхронизировать
        </button>
      </div>

      {syncMsg && (
        <div className="flex items-center gap-2 text-xs text-green-400 mb-3">
          <CheckCircle size={13} /> {syncMsg}
        </div>
      )}

      {user.subscription_conflict && (
        <div className="rounded-input bg-red-500/10 border border-red-500/20 px-4 py-3 mb-4">
          <div className="flex items-center gap-2 text-sm text-red-400 mb-2">
            <AlertTriangle size={15} />
            Конфликт подписки — укажите Remnawave UUID для сохранения
          </div>
          <p className="text-xs text-text-muted mb-2">
            Текущий: <span className="font-mono">{user.remnawave_uuid ?? '—'}</span>
          </p>
          <div className="flex gap-2">
            <input
              value={resolveUuid}
              onChange={(e) => setResolveUuid(e.target.value)}
              placeholder="UUID для сохранения"
              className="flex-1 rounded-input bg-background border border-red-500/30 px-2.5 py-1.5 text-xs text-text-primary font-mono focus:outline-none focus:border-red-400"
            />
            <button
              onClick={() => resolveMutation.mutate({ remnawave_uuid: resolveUuid })}
              disabled={resolveMutation.isPending || !resolveUuid.trim()}
              className="text-xs px-2.5 py-1.5 rounded-input bg-red-500/20 text-red-300 hover:bg-red-500/30 disabled:opacity-50 transition-colors"
            >
              Разрешить
            </button>
          </div>
        </div>
      )}

      {resolveMsg && (
        <div className="flex items-center gap-2 text-xs text-green-400 mb-3">
          <CheckCircle size={13} /> {resolveMsg}
        </div>
      )}

      {/* Info */}
      <div className="rounded-card bg-surface border border-border-neutral p-4 mb-4">
        <h2 className="text-sm font-semibold text-text-primary mb-3">Информация</h2>
        <div className="flex flex-col gap-2">
          {[
            ['ID', user.id],
            ['Remnawave UUID', user.remnawave_uuid ?? '—'],
            ['Оплачивал', user.has_made_payment ? 'Да' : 'Нет'],
            ['Создан', new Date(user.created_at).toLocaleString('ru-RU')],
            ['Последняя активность', new Date(user.last_seen_at).toLocaleString('ru-RU')],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-3 text-sm">
              <span className="text-text-muted shrink-0">{label}</span>
              <span className="text-text-secondary text-right break-all">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Subscription */}
      {user.subscription && (
        <div className="rounded-card bg-surface border border-border-neutral p-4 mb-4">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Подписка</h2>
          <div className="flex flex-col gap-2">
            {[
              ['Тип', user.subscription.type === 'trial' ? 'Пробная' : 'Платная'],
              ['Статус', user.subscription.status],
              ['Истекает', new Date(user.subscription.expires_at).toLocaleDateString('ru-RU')],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-3 text-sm">
                <span className="text-text-muted">{label}</span>
                <span className="text-text-secondary">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Transactions */}
      {user.recent_transactions.length > 0 && (
        <div className="rounded-card bg-surface border border-border-neutral p-4">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Последние транзакции</h2>
          <div className="flex flex-col gap-1">
            {user.recent_transactions.map((tx) => (
              <div
                key={tx.id}
                className="flex items-center justify-between gap-3 py-1.5 border-b border-border-neutral last:border-0"
              >
                <div>
                  <span className="text-xs text-text-primary">{tx.type}</span>
                  {tx.days_added && (
                    <span className="ml-2 text-xs text-text-muted">+{tx.days_added}д</span>
                  )}
                </div>
                <div className="text-right">
                  {tx.amount_rub && (
                    <span className="text-xs text-text-secondary">{tx.amount_rub} ₽</span>
                  )}
                  <span
                    className={`ml-2 text-xs ${
                      tx.status === 'completed'
                        ? 'text-green-400'
                        : tx.status === 'failed'
                        ? 'text-red-400'
                        : 'text-text-muted'
                    }`}
                  >
                    {tx.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

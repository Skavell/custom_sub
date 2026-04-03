// frontend/src/pages/admin/AdminPromoCodesPage.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { PromoCodeAdminItem, PromoCodeCreateRequest } from '@/types/api'

const EMPTY_FORM: PromoCodeCreateRequest = {
  code: '',
  type: 'bonus_days',
  value: 7,
  max_uses: null,
  valid_until: null,
}

export default function AdminPromoCodesPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<PromoCodeCreateRequest>(EMPTY_FORM)
  const [createError, setCreateError] = useState<string | null>(null)

  const { data: codes, isLoading, error } = useQuery<PromoCodeAdminItem[]>({
    queryKey: ['admin-promo-codes'],
    queryFn: () => api.get<PromoCodeAdminItem[]>('/api/admin/promo-codes'),
    staleTime: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: (data: PromoCodeCreateRequest) =>
      api.post<PromoCodeAdminItem>('/api/admin/promo-codes', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-promo-codes'] })
      setForm(EMPTY_FORM)
      setShowForm(false)
      setCreateError(null)
    },
    onError: (e) => {
      setCreateError(e instanceof ApiError ? e.detail : 'Ошибка создания')
    },
  })

  const toggleMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/api/admin/promo-codes/${id}/toggle`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-promo-codes'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/admin/promo-codes/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-promo-codes'] }),
  })

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-text-primary">Промокоды</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-accent text-background text-xs font-medium hover:bg-accent-hover transition-colors"
        >
          <Plus size={14} /> Создать
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-card bg-surface border border-border-accent p-4 mb-5">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Новый промокод</h2>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <label className="col-span-2 flex flex-col gap-1">
              <span className="text-xs text-text-muted">Код</span>
              <input
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                placeholder="SUMMER2026"
                className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-text-muted">Тип</span>
              <select
                value={form.type}
                onChange={(e) =>
                  setForm((f) => ({ ...f, type: e.target.value as PromoCodeCreateRequest['type'] }))
                }
                className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              >
                <option value="bonus_days">Бонусные дни</option>
                <option value="discount_percent">Скидка %</option>
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-text-muted">
                {form.type === 'bonus_days' ? 'Дней' : 'Процент'}
              </span>
              <input
                type="number"
                value={form.value}
                onChange={(e) => setForm((f) => ({ ...f, value: Number(e.target.value) }))}
                className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-text-muted">Макс. использований</span>
              <input
                type="number"
                value={form.max_uses ?? ''}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    max_uses: e.target.value === '' ? null : Number(e.target.value),
                  }))
                }
                placeholder="∞"
                className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-text-muted">Действует до</span>
              <input
                type="date"
                value={form.valid_until ?? ''}
                onChange={(e) =>
                  setForm((f) => ({ ...f, valid_until: e.target.value || null }))
                }
                className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </label>
          </div>
          {createError && <p className="text-xs text-red-400 mb-2">{createError}</p>}
          <div className="flex gap-2">
            <button
              onClick={() => createMutation.mutate(form)}
              disabled={createMutation.isPending || !form.code}
              className="px-4 py-1.5 rounded-input bg-accent text-background text-xs font-medium disabled:opacity-50 transition-colors"
            >
              Создать
            </button>
            <button
              onClick={() => { setShowForm(false); setCreateError(null); setForm(EMPTY_FORM) }}
              className="px-4 py-1.5 rounded-input bg-white/5 text-text-secondary text-xs hover:text-text-primary transition-colors"
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400">
          {error instanceof ApiError ? error.detail : 'Ошибка загрузки'}
        </p>
      )}

      <div className="flex flex-col gap-1">
        {codes?.map((code) => (
          <div
            key={code.id}
            className="flex items-center gap-3 rounded-input bg-surface border border-border-neutral px-4 py-3"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-mono font-medium text-text-primary">{code.code}</span>
                {!code.is_active && (
                  <span className="text-xs bg-white/5 text-text-muted px-1.5 py-0.5 rounded">неактивен</span>
                )}
              </div>
              <div className="flex items-center gap-3 mt-0.5 text-xs text-text-muted flex-wrap">
                <span>
                  {code.type === 'bonus_days' ? `+${code.value}д` : `${code.value}%`}
                </span>
                <span>
                  использований: {code.used_count}{code.max_uses != null ? `/${code.max_uses}` : ''}
                </span>
                {code.valid_until && (
                  <span>до {new Date(code.valid_until).toLocaleDateString('ru-RU')}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() => toggleMutation.mutate(code.id)}
                disabled={toggleMutation.isPending}
                title={code.is_active ? 'Отключить' : 'Включить'}
                className="p-1.5 rounded-input text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
              >
                {code.is_active ? <ToggleRight size={16} className="text-accent" /> : <ToggleLeft size={16} />}
              </button>
              <button
                onClick={() => {
                  if (confirm(`Удалить промокод ${code.code}?`)) deleteMutation.mutate(code.id)
                }}
                disabled={deleteMutation.isPending}
                className="p-1.5 rounded-input text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
        {codes?.length === 0 && (
          <p className="text-sm text-text-muted text-center py-8">Промокоды не созданы</p>
        )}
      </div>
    </div>
  )
}

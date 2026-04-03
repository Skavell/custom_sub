// frontend/src/pages/admin/AdminPlansPage.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Pencil, X, Check } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { PlanAdminItem, PlanAdminUpdateRequest } from '@/types/api'

function PlanRow({ plan }: { plan: PlanAdminItem }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<PlanAdminUpdateRequest>({
    price_rub: plan.price_rub,
    new_user_price_rub: plan.new_user_price_rub ?? undefined,
    duration_days: plan.duration_days,
    label: plan.label,
    is_active: plan.is_active,
  })
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (data: PlanAdminUpdateRequest) =>
      api.patch<PlanAdminItem>(`/api/admin/plans/${plan.id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-plans'] })
      setEditing(false)
      setSaveError(null)
    },
    onError: (e) => {
      setSaveError(e instanceof ApiError ? e.detail : 'Ошибка сохранения')
    },
  })

  if (!editing) {
    return (
      <div className="flex items-center gap-3 rounded-input bg-surface border border-border-neutral px-4 py-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-primary">{plan.name}</span>
            {plan.label && (
              <span className="text-xs bg-accent/10 text-accent px-1.5 py-0.5 rounded">{plan.label}</span>
            )}
            {!plan.is_active && (
              <span className="text-xs bg-white/5 text-text-muted px-1.5 py-0.5 rounded">неактивен</span>
            )}
          </div>
          <div className="flex items-center gap-4 mt-0.5 text-xs text-text-muted">
            <span>{plan.duration_days}д</span>
            <span>{plan.price_rub} ₽</span>
            {plan.new_user_price_rub != null && (
              <span>{plan.new_user_price_rub} ₽ (новый)</span>
            )}
          </div>
        </div>
        <button
          onClick={() => setEditing(true)}
          className="p-1.5 rounded-input text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
        >
          <Pencil size={14} />
        </button>
      </div>
    )
  }

  return (
    <div className="rounded-input bg-surface border border-border-accent px-4 py-3">
      <div className="grid grid-cols-2 gap-3 mb-3">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Метка</span>
          <input
            value={form.label ?? ''}
            onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Дней</span>
          <input
            type="number"
            value={form.duration_days ?? ''}
            onChange={(e) => setForm((f) => ({ ...f, duration_days: Number(e.target.value) }))}
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Цена (₽)</span>
          <input
            type="number"
            value={form.price_rub ?? ''}
            onChange={(e) => setForm((f) => ({ ...f, price_rub: Number(e.target.value) }))}
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Цена новому (₽)</span>
          <input
            type="number"
            value={form.new_user_price_rub ?? ''}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                new_user_price_rub: e.target.value === '' ? null : Number(e.target.value),
              }))
            }
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
      </div>
      <label className="flex items-center gap-2 mb-3 cursor-pointer">
        <input
          type="checkbox"
          checked={form.is_active ?? false}
          onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
          className="rounded accent-cyan-500"
        />
        <span className="text-sm text-text-secondary">Активен</span>
      </label>
      {saveError && <p className="text-xs text-red-400 mb-2">{saveError}</p>}
      <div className="flex gap-2">
        <button
          onClick={() => mutation.mutate(form)}
          disabled={mutation.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-accent text-background text-xs font-medium disabled:opacity-50 transition-colors"
        >
          <Check size={13} /> Сохранить
        </button>
        <button
          onClick={() => { setEditing(false); setSaveError(null) }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-white/5 text-text-secondary text-xs hover:text-text-primary transition-colors"
        >
          <X size={13} /> Отмена
        </button>
      </div>
    </div>
  )
}

export default function AdminPlansPage() {
  const { data: plans, isLoading, error } = useQuery<PlanAdminItem[]>({
    queryKey: ['admin-plans'],
    queryFn: () => api.get<PlanAdminItem[]>('/api/admin/plans'),
    staleTime: 60_000,
  })

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Тарифы</h1>

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

      <div className="flex flex-col gap-2">
        {plans?.map((plan) => <PlanRow key={plan.id} plan={plan} />)}
      </div>
    </div>
  )
}

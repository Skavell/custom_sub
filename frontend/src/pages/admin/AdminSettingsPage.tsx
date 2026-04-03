// frontend/src/pages/admin/AdminSettingsPage.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Eye, EyeOff } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { SettingAdminItem } from '@/types/api'

function SettingRow({ setting }: { setting: SettingAdminItem }) {
  const queryClient = useQueryClient()
  const [value, setValue] = useState(setting.value ?? '')
  const [showValue, setShowValue] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setSaved(true)
      setSaveError(null)
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-text-muted">{setting.key}</span>
        {setting.is_sensitive && (
          <span className="text-xs bg-yellow-500/10 text-yellow-400 px-1.5 py-0.5 rounded">
            скрытое
          </span>
        )}
      </div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type={setting.is_sensitive && !showValue ? 'password' : 'text'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={setting.is_sensitive ? '••••••••' : 'Значение'}
            className="w-full rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
          {setting.is_sensitive && (
            <button
              onClick={() => setShowValue((v) => !v)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
            >
              {showValue ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          )}
        </div>
        <button
          onClick={() => mutation.mutate(value)}
          disabled={mutation.isPending}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-input text-xs font-medium transition-colors ${
            saved
              ? 'bg-green-500/20 text-green-400'
              : 'bg-accent/10 text-accent hover:bg-accent/20'
          } disabled:opacity-50`}
        >
          <Save size={13} />
          {saved ? 'Сохранено' : 'Сохранить'}
        </button>
      </div>
      {saveError && <p className="mt-1 text-xs text-red-400">{saveError}</p>}
    </div>
  )
}

export default function AdminSettingsPage() {
  const { data: settings, isLoading, error } = useQuery<SettingAdminItem[]>({
    queryKey: ['admin-settings'],
    queryFn: () => api.get<SettingAdminItem[]>('/api/admin/settings'),
    staleTime: 60_000,
  })

  const regular = settings?.filter((s) => !s.is_sensitive) ?? []
  const sensitive = settings?.filter((s) => s.is_sensitive) ?? []

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Настройки</h1>

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

      {regular.length > 0 && (
        <div className="mb-5">
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2 px-1">
            Основные
          </h2>
          <div className="flex flex-col gap-2">
            {regular.map((s) => <SettingRow key={s.key} setting={s} />)}
          </div>
        </div>
      )}

      {sensitive.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2 px-1">
            Секреты / токены
          </h2>
          <div className="flex flex-col gap-2">
            {sensitive.map((s) => <SettingRow key={s.key} setting={s} />)}
          </div>
        </div>
      )}
    </div>
  )
}

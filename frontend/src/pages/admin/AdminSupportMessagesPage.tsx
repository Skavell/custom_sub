// frontend/src/pages/admin/AdminSupportMessagesPage.tsx
// Note: endpoint returns plain list[SupportMessageAdminItem], NOT a paginated wrapper.
// Uses ?skip=N&limit=50 for load-more.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import type { SupportMessageAdminItem } from '@/types/api'

const PAGE_SIZE = 50

export default function AdminSupportMessagesPage() {
  const [skip, setSkip] = useState(0)

  const { data, isLoading, error } = useQuery<SupportMessageAdminItem[]>({
    queryKey: ['admin-support-messages', skip],
    queryFn: () =>
      api.get<SupportMessageAdminItem[]>(
        `/api/admin/support-messages?skip=${skip}&limit=${PAGE_SIZE}`,
      ),
    staleTime: 30_000,
  })

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Сообщения поддержки</h1>

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
        {data?.length === 0 && (
          <p className="text-sm text-text-muted text-center py-8">Сообщений нет</p>
        )}
        {data?.map((msg) => (
          <div
            key={msg.id}
            className="rounded-card bg-surface border border-border-neutral px-4 py-3"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm font-medium text-text-primary">{msg.display_name}</span>
              <span className="text-xs text-text-muted">
                {new Date(msg.created_at).toLocaleString('ru-RU')}
              </span>
            </div>
            <p className="text-sm text-text-secondary whitespace-pre-wrap">{msg.message}</p>
          </div>
        ))}
      </div>

      {/* Load more (endpoint returns up to 50 per page) */}
      {data && data.length === PAGE_SIZE && (
        <button
          onClick={() => setSkip((s) => s + PAGE_SIZE)}
          className="mt-4 w-full py-2 rounded-input text-sm text-accent bg-surface border border-border-neutral hover:border-border-accent transition-colors"
        >
          Загрузить ещё
        </button>
      )}
      {skip > 0 && (
        <button
          onClick={() => setSkip(0)}
          className="mt-2 w-full py-1.5 rounded-input text-xs text-text-muted hover:text-text-primary transition-colors"
        >
          В начало
        </button>
      )}
    </div>
  )
}

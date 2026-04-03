import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search, AlertTriangle } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { PaginatedUsers } from '@/types/api'

export default function AdminUsersPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery<PaginatedUsers>({
    queryKey: ['admin-users', page, search],
    queryFn: () =>
      api.get<PaginatedUsers>(
        `/api/admin/users?page=${page}&per_page=20&search=${encodeURIComponent(search)}`,
      ),
    staleTime: 30_000,
  })

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Пользователи</h1>

      <div className="relative mb-4">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
        <input
          type="text"
          placeholder="Поиск по имени..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          className="w-full rounded-input bg-surface border border-border-neutral pl-9 pr-4 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
        />
      </div>

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

      {data && (
        <>
          <div className="flex flex-col gap-1">
            {data.items.length === 0 && (
              <p className="text-sm text-text-muted text-center py-8">Пользователи не найдены</p>
            )}
            {data.items.map((user) => (
              <button
                key={user.id}
                onClick={() => navigate(`/admin/users/${user.id}`)}
                className="flex items-center gap-3 rounded-input bg-surface border border-border-neutral px-4 py-3 text-left hover:border-border-accent transition-colors w-full"
              >
                <div className="h-8 w-8 rounded-full bg-accent/20 flex items-center justify-center text-xs font-bold text-accent shrink-0">
                  {user.display_name[0]?.toUpperCase() ?? '?'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-text-primary truncate">
                      {user.display_name}
                    </span>
                    {user.subscription_conflict && (
                      <span className="flex items-center gap-1 text-xs bg-red-500/15 text-red-400 px-1.5 py-0.5 rounded">
                        <AlertTriangle size={10} />
                        конфликт
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                    <span className="text-xs text-text-muted">
                      {user.providers.join(', ')}
                    </span>
                    {user.subscription_status && (
                      <span
                        className={`text-xs ${
                          user.subscription_status === 'active'
                            ? 'text-green-400'
                            : 'text-text-muted'
                        }`}
                      >
                        {user.subscription_status === 'active'
                          ? 'активна'
                          : user.subscription_status === 'expired'
                          ? 'истекла'
                          : user.subscription_status}
                      </span>
                    )}
                    {user.subscription_expires_at && (
                      <span className="text-xs text-text-muted">
                        до {new Date(user.subscription_expires_at).toLocaleDateString('ru-RU')}
                      </span>
                    )}
                  </div>
                </div>
                <span className="text-xs text-text-muted shrink-0">
                  {new Date(user.created_at).toLocaleDateString('ru-RU')}
                </span>
              </button>
            ))}
          </div>

          {data.total > 20 && (
            <div className="flex items-center justify-between mt-4">
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
                className="text-sm text-accent disabled:text-text-muted disabled:cursor-not-allowed"
              >
                ← Назад
              </button>
              <span className="text-xs text-text-muted">
                {(page - 1) * 20 + 1}–{Math.min(page * 20, data.total)} из {data.total}
              </span>
              <button
                disabled={page * 20 >= data.total}
                onClick={() => setPage((p) => p + 1)}
                className="text-sm text-accent disabled:text-text-muted disabled:cursor-not-allowed"
              >
                Вперёд →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

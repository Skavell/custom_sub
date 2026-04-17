import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search, AlertTriangle } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { UserAdminListItem } from '@/types/api'

const PAGE_SIZE = 50

export default function AdminUsersPage() {
  const [search, setSearch] = useState('')
  const [skip, setSkip] = useState(0)
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery<UserAdminListItem[]>({
    queryKey: ['admin-users', skip, search],
    queryFn: () =>
      api.get<UserAdminListItem[]>(
        `/api/admin/users?skip=${skip}&limit=${PAGE_SIZE}${search ? `&q=${encodeURIComponent(search)}` : ''}`,
      ),
    staleTime: 30_000,
  })

  function handleSearch(value: string) {
    setSearch(value)
    setSkip(0)
  }

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Пользователи</h1>

      <div className="relative mb-4">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
        <input
          type="text"
          placeholder="Поиск по имени, email, UUID, #ID..."
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
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
            {data.length === 0 && (
              <p className="text-sm text-text-muted text-center py-8">Пользователи не найдены</p>
            )}
            {data.map((user) => (
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

          <div className="flex items-center justify-between mt-4">
            {skip > 0 && (
              <button
                onClick={() => setSkip((s) => Math.max(0, s - PAGE_SIZE))}
                className="text-sm text-accent"
              >
                ← Назад
              </button>
            )}
            <div className="flex-1" />
            {data.length === PAGE_SIZE && (
              <button
                onClick={() => setSkip((s) => s + PAGE_SIZE)}
                className="text-sm text-accent"
              >
                Ещё →
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'

interface AdminTicket {
  id: string
  number: number
  subject: string
  status: 'open' | 'closed'
  user_display_name: string
  user_email: string | null
  message_count: number
  updated_at: string
}

export function AdminSupportMessagesPage() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [search, setSearch] = useState('')

  const params = new URLSearchParams()
  if (statusFilter) params.set('status', statusFilter)
  if (search) params.set('search', search)

  const { data: tickets = [] } = useQuery<AdminTicket[]>({
    queryKey: ['admin-support-tickets', statusFilter, search],
    queryFn: () => api.get(`/api/admin/support-tickets?${params.toString()}`),
  })

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-6">Обращения</h1>

      <div className="flex gap-3 mb-4">
        <input
          className="rounded-input border border-border-neutral bg-background px-3 py-2 text-sm text-text-primary flex-1 focus:outline-none"
          placeholder="Поиск по теме..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select
          className="rounded-input border border-border-neutral bg-background px-3 py-2 text-sm text-text-secondary"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
        >
          <option value="">Все</option>
          <option value="open">Открытые</option>
          <option value="closed">Закрытые</option>
        </select>
      </div>

      <div className="flex flex-col gap-2">
        {tickets.map(ticket => (
          <button
            key={ticket.id}
            onClick={() => navigate(`/admin/support-tickets/${ticket.id}`)}
            className="rounded-card border border-border-neutral bg-surface p-4 flex items-center gap-4 hover:border-text-muted transition-colors text-left w-full"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-accent font-mono">#{ticket.number}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  ticket.status === 'open'
                    ? 'bg-yellow-500/10 text-yellow-400'
                    : 'bg-green-500/10 text-green-400'
                }`}>
                  {ticket.status === 'open' ? 'Открыто' : 'Закрыто'}
                </span>
                <span className="text-xs text-text-muted">{ticket.message_count} сообщ.</span>
              </div>
              <p className="text-sm text-text-primary truncate">{ticket.subject}</p>
              <p className="text-xs text-text-muted">{ticket.user_display_name} · {ticket.user_email ?? 'нет email'}</p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-xs text-text-muted">{new Date(ticket.updated_at).toLocaleString('ru')}</p>
              <ChevronRight size={16} className="text-text-muted mt-1 ml-auto" />
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

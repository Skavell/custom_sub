import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MessageCircle, ChevronRight, Plus } from 'lucide-react'
import { api } from '@/lib/api'

interface SupportTicket {
  id: string
  number: number
  subject: string
  status: 'open' | 'closed'
  updated_at: string
  unread_count: number
}

interface CreateTicketPayload {
  subject: string
  text: string
}

export function SupportPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [subject, setSubject] = useState('')
  const [text, setText] = useState('')
  const [showForm, setShowForm] = useState(false)

  const { data: tickets = [] } = useQuery<SupportTicket[]>({
    queryKey: ['support-tickets'],
    queryFn: () => api.get('/api/support/tickets'),
  })

  const createMutation = useMutation({
    mutationFn: (payload: CreateTicketPayload) =>
      api.post('/api/support/tickets', payload),
    onSuccess: (ticket: any) => {
      queryClient.invalidateQueries({ queryKey: ['support-tickets'] })
      navigate(`/support/${ticket.id}`)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!subject.trim() || !text.trim()) return
    createMutation.mutate({ subject: subject.trim(), text: text.trim() })
  }

  return (
    <div className="max-w-xl mx-auto py-6 px-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-text-primary">Поддержка</h1>
        <button
          onClick={() => setShowForm(v => !v)}
          className="flex items-center gap-1.5 text-sm text-accent hover:text-accent/80 transition-colors"
        >
          <Plus size={16} />
          Новое обращение
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="rounded-card border border-border-neutral bg-surface p-4 mb-6"
        >
          <h2 className="text-sm font-semibold text-text-primary mb-4">Новое обращение</h2>
          <div className="flex flex-col gap-3">
            <div>
              <label className="text-xs text-text-muted mb-1 block">Тема обращения</label>
              <input
                className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
                placeholder="Например: не работает подключение"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                maxLength={255}
              />
            </div>
            <div>
              <label className="text-xs text-text-muted mb-1 block">Описание</label>
              <textarea
                className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent resize-none"
                placeholder="Подробно опиши что происходит..."
                rows={4}
                value={text}
                onChange={e => setText(e.target.value)}
                maxLength={2000}
              />
              <div className="text-xs text-text-muted text-right mt-1">{text.length}/2000</div>
            </div>
            <button
              type="submit"
              disabled={!subject.trim() || !text.trim() || createMutation.isPending}
              className="flex items-center justify-center gap-2 rounded-input bg-accent text-white py-2 text-sm font-medium disabled:opacity-50"
            >
              {createMutation.isPending ? 'Отправка...' : (
                <>
                  Отправить
                  <MessageCircle size={15} />
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {tickets.length === 0 ? (
        <div className="text-center py-12 text-text-muted text-sm">
          Обращений пока нет
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {tickets.map(ticket => (
            <button
              key={ticket.id}
              onClick={() => navigate(`/support/${ticket.id}`)}
              className="rounded-card border border-border-neutral bg-surface p-4 flex items-center gap-3 hover:border-text-muted transition-colors text-left w-full"
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
                  {ticket.unread_count > 0 && (
                    <span className="ml-auto text-xs bg-accent text-white px-1.5 py-0.5 rounded-full">
                      {ticket.unread_count}
                    </span>
                  )}
                </div>
                <p className="text-sm text-text-primary truncate">{ticket.subject}</p>
                <p className="text-xs text-text-muted mt-0.5">{new Date(ticket.updated_at).toLocaleString('ru')}</p>
              </div>
              <ChevronRight size={16} className="text-text-muted flex-shrink-0" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Send } from 'lucide-react'
import { api } from '@/lib/api'

interface SupportMessage {
  id: string
  author_type: 'user' | 'admin'
  text: string
  created_at: string
}

interface SupportTicketDetail {
  id: string
  number: number
  subject: string
  status: 'open' | 'closed'
  messages: SupportMessage[]
}

export function SupportTicketPage() {
  const { ticketId } = useParams<{ ticketId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [replyText, setReplyText] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: ticket, isLoading } = useQuery<SupportTicketDetail>({
    queryKey: ['support-ticket', ticketId],
    queryFn: () => api.get(`/api/support/tickets/${ticketId}`),
    enabled: !!ticketId,
  })

  const replyMutation = useMutation({
    mutationFn: (text: string) =>
      api.post(`/api/support/tickets/${ticketId}/messages`, { text }),
    onSuccess: () => {
      setReplyText('')
      queryClient.invalidateQueries({ queryKey: ['support-ticket', ticketId] })
      queryClient.invalidateQueries({ queryKey: ['support-tickets'] })
    },
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [ticket?.messages.length])

  if (isLoading) {
    return <div className="flex justify-center py-12"><span className="text-text-muted text-sm">Загрузка...</span></div>
  }

  if (!ticket) return null

  return (
    <div className="max-w-xl mx-auto py-6 px-4 flex flex-col" style={{ minHeight: 'calc(100vh - 80px)' }}>
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => navigate('/support')} className="text-text-muted hover:text-text-secondary">
          <ChevronLeft size={20} />
        </button>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-accent font-mono text-sm font-semibold">#{ticket.number}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              ticket.status === 'open'
                ? 'bg-yellow-500/10 text-yellow-400'
                : 'bg-green-500/10 text-green-400'
            }`}>
              {ticket.status === 'open' ? 'Открыто' : 'Закрыто'}
            </span>
          </div>
          <h1 className="text-sm font-semibold text-text-primary mt-0.5">{ticket.subject}</h1>
        </div>
      </div>

      <div className="flex-1 flex flex-col gap-3 mb-4 overflow-y-auto">
        {ticket.messages.map(msg => (
          <div
            key={msg.id}
            className={`flex ${msg.author_type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[85%] rounded-card px-3 py-2.5 ${
              msg.author_type === 'user'
                ? 'bg-accent/10 border border-accent/30 rounded-br-sm'
                : 'bg-surface border border-border-neutral rounded-bl-sm'
            }`}>
              <p className={`text-xs mb-1 ${
                msg.author_type === 'user' ? 'text-accent' : 'text-text-muted'
              }`}>
                {msg.author_type === 'user' ? 'Вы' : 'Поддержка'} · {new Date(msg.created_at).toLocaleString('ru')}
              </p>
              <p className="text-sm text-text-primary whitespace-pre-wrap">{msg.text}</p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {ticket.status === 'open' ? (
        <div className="rounded-card border border-border-neutral bg-surface p-3">
          <textarea
            className="w-full bg-background rounded-input border border-border-neutral px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent resize-none mb-2"
            rows={2}
            placeholder="Написать ответ..."
            value={replyText}
            onChange={e => setReplyText(e.target.value)}
            maxLength={2000}
          />
          <div className="flex justify-between items-center">
            <span className="text-xs text-text-muted">{replyText.length}/2000</span>
            <button
              onClick={() => replyMutation.mutate(replyText.trim())}
              disabled={!replyText.trim() || replyMutation.isPending}
              className="flex items-center gap-1.5 bg-accent text-white text-sm px-3 py-1.5 rounded-input disabled:opacity-50"
            >
              <Send size={13} />
              {replyMutation.isPending ? 'Отправка...' : 'Отправить'}
            </button>
          </div>
        </div>
      ) : (
        <div className="text-center py-3 text-text-muted text-sm border border-border-neutral rounded-card">
          Обращение закрыто
        </div>
      )}
    </div>
  )
}

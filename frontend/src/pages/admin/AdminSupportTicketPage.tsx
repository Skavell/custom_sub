import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Send } from 'lucide-react'
import { api } from '@/lib/api'

interface SupportMessage {
  id: string
  author_type: 'user' | 'admin'
  text: string
  created_at: string
}

interface AdminTicketDetail {
  id: string
  number: number
  subject: string
  status: 'open' | 'closed'
  user_id: string
  messages: SupportMessage[]
}

interface UserInfo {
  id: string
  display_name: string
  subscription: { type: string; status: string } | null
  created_at: string
}

export function AdminSupportTicketPage() {
  const { ticketId } = useParams<{ ticketId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [replyText, setReplyText] = useState('')

  const { data: ticket } = useQuery<AdminTicketDetail>({
    queryKey: ['admin-support-ticket', ticketId],
    queryFn: () => api.get(`/api/admin/support-tickets/${ticketId}`),
    enabled: !!ticketId,
  })

  const { data: userInfo } = useQuery<UserInfo>({
    queryKey: ['admin-user', ticket?.user_id],
    queryFn: () => api.get(`/api/admin/users/${ticket?.user_id}`),
    enabled: !!ticket?.user_id,
  })

  const replyMutation = useMutation({
    mutationFn: (text: string) =>
      api.post(`/api/admin/support-tickets/${ticketId}/messages`, { text }),
    onSuccess: () => {
      setReplyText('')
      queryClient.invalidateQueries({ queryKey: ['admin-support-ticket', ticketId] })
    },
  })

  const closeMutation = useMutation({
    mutationFn: () => api.post(`/api/admin/support-tickets/${ticketId}/close`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-support-ticket', ticketId] })
    },
  })

  if (!ticket) return null

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/admin/support-messages')} className="text-text-muted">
          <ChevronLeft size={20} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-accent font-mono font-semibold">#{ticket.number}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              ticket.status === 'open'
                ? 'bg-yellow-500/10 text-yellow-400'
                : 'bg-green-500/10 text-green-400'
            }`}>
              {ticket.status === 'open' ? 'Открыто' : 'Закрыто'}
            </span>
          </div>
          <h1 className="text-lg font-semibold text-text-primary">{ticket.subject}</h1>
        </div>
        {ticket.status === 'open' && (
          <button
            onClick={() => closeMutation.mutate()}
            disabled={closeMutation.isPending}
            className="text-sm bg-surface border border-border-neutral px-3 py-1.5 rounded-input text-text-secondary hover:text-text-primary"
          >
            ✓ Закрыть обращение
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 flex flex-col gap-3">
          {ticket.messages.map(msg => (
            <div
              key={msg.id}
              className={`flex ${msg.author_type === 'user' ? 'justify-start' : 'justify-end'}`}
            >
              <div className={`max-w-[85%] rounded-card px-3 py-2.5 ${
                msg.author_type === 'user'
                  ? 'bg-surface border border-border-neutral rounded-bl-sm'
                  : 'bg-accent/10 border border-accent/30 rounded-br-sm'
              }`}>
                <p className={`text-xs mb-1 ${msg.author_type === 'admin' ? 'text-accent' : 'text-text-muted'}`}>
                  {msg.author_type === 'admin' ? 'Поддержка (вы)' : userInfo?.display_name ?? 'Пользователь'}
                  {' · '}{new Date(msg.created_at).toLocaleString('ru')}
                </p>
                <p className="text-sm text-text-primary whitespace-pre-wrap">{msg.text}</p>
              </div>
            </div>
          ))}

          {ticket.status === 'open' && (
            <div className="rounded-card border border-border-neutral bg-surface p-3 mt-2">
              <textarea
                className="w-full bg-background rounded-input border border-border-neutral px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent resize-none mb-2"
                rows={3}
                placeholder="Написать ответ..."
                value={replyText}
                onChange={e => setReplyText(e.target.value)}
              />
              <div className="flex justify-between items-center">
                <span className="text-xs text-text-muted">↩ Пользователь получит уведомление</span>
                <button
                  onClick={() => replyMutation.mutate(replyText.trim())}
                  disabled={!replyText.trim() || replyMutation.isPending}
                  className="flex items-center gap-1.5 bg-accent text-white text-sm px-3 py-1.5 rounded-input disabled:opacity-50"
                >
                  <Send size={13} />
                  Ответить
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="rounded-card border border-border-neutral bg-surface p-4 h-fit">
          <h3 className="text-xs font-semibold text-text-muted uppercase mb-3">Пользователь</h3>
          <p className="text-sm font-medium text-text-primary mb-0.5">{userInfo?.display_name}</p>
          {userInfo?.subscription ? (
            <p className={`text-xs mb-2 ${
              userInfo.subscription.status === 'active' ? 'text-green-400' : 'text-text-muted'
            }`}>
              {userInfo.subscription.type === 'trial' ? 'Триал' : 'Платная'} ·{' '}
              {userInfo.subscription.status === 'active' ? 'активна' : 'истекла'}
            </p>
          ) : (
            <p className="text-xs text-text-muted mb-2">Нет подписки</p>
          )}
          {userInfo && (
            <p className="text-xs text-text-muted mb-3">
              Регистрация: {new Date(userInfo.created_at).toLocaleDateString('ru')}
            </p>
          )}
          {ticket.user_id && (
            <Link
              to={`/admin/users/${ticket.user_id}`}
              className="text-xs text-accent hover:underline"
            >
              Открыть профиль →
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}

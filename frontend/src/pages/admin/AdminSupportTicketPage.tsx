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

interface SubscriptionInfo {
  type: string
  status: string
  expires_at: string
}

interface ProviderInfo {
  provider: string
  email_verified: boolean | null
}

interface UserInfo {
  id: string
  display_name: string
  email: string | null
  avatar_url: string | null
  is_banned: boolean
  has_made_payment: boolean
  created_at: string
  last_seen_at: string
  subscription: SubscriptionInfo | null
  providers: ProviderInfo[]
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

        <div className="rounded-card border border-border-neutral bg-surface p-4 h-fit space-y-2.5">
          <h3 className="text-xs font-semibold text-text-muted uppercase">Пользователь</h3>

          {userInfo ? (
            <>
              <div>
                <p className="text-sm font-medium text-text-primary">{userInfo.display_name}</p>
                {userInfo.email && (
                  <p className="text-xs text-text-muted">{userInfo.email}</p>
                )}
                {userInfo.is_banned && (
                  <span className="text-xs text-red-400">⛔ забанен</span>
                )}
              </div>

              <div className="border-t border-border-neutral pt-2 space-y-1">
                {userInfo.subscription ? (
                  <>
                    <p className={`text-xs font-medium ${
                      userInfo.subscription.status === 'active' ? 'text-green-400' : 'text-yellow-400'
                    }`}>
                      {userInfo.subscription.type === 'trial' ? 'Триал' : 'Платная подписка'} ·{' '}
                      {userInfo.subscription.status === 'active' ? 'активна' : 'истекла'}
                    </p>
                    <p className="text-xs text-text-muted">
                      До: {new Date(userInfo.subscription.expires_at).toLocaleDateString('ru')}
                    </p>
                  </>
                ) : (
                  <p className="text-xs text-text-muted">Нет подписки</p>
                )}
                <p className="text-xs text-text-muted">
                  Платил: {userInfo.has_made_payment ? 'да' : 'нет'}
                </p>
              </div>

              <div className="border-t border-border-neutral pt-2 space-y-1">
                <p className="text-xs text-text-muted">
                  Регистрация: {new Date(userInfo.created_at).toLocaleDateString('ru')}
                </p>
                <p className="text-xs text-text-muted">
                  Был: {new Date(userInfo.last_seen_at).toLocaleString('ru')}
                </p>
                {userInfo.providers.length > 0 && (
                  <p className="text-xs text-text-muted">
                    Вход: {userInfo.providers.map(p => p.provider).join(', ')}
                  </p>
                )}
              </div>

              <div className="border-t border-border-neutral pt-2">
                <Link
                  to={`/admin/users/${ticket.user_id}`}
                  className="text-xs text-accent hover:underline"
                >
                  Открыть карточку →
                </Link>
              </div>
            </>
          ) : (
            <p className="text-xs text-text-muted">Загрузка...</p>
          )}
        </div>
      </div>
    </div>
  )
}

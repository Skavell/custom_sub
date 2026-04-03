import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Send, MessageCircle, Loader2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { api, ApiError } from '@/lib/api'

export default function SupportPage() {
  const { user } = useAuth()
  const [message, setMessage] = useState('')
  const [sent, setSent] = useState(false)

  const mutation = useMutation({
    mutationFn: () => api.post('/api/support/message', { message: message.trim() }),
    onSuccess: () => {
      setSent(true)
      setMessage('')
    },
  })

  return (
    <div className="p-4 md:p-6 max-w-xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-1">Поддержка</h1>
      <p className="text-sm text-text-muted mb-6">Мы поможем решить любую проблему</p>

      {/* Telegram */}
      <div className="rounded-card bg-surface border border-border-neutral p-4 mb-4 flex items-center gap-3">
        <div className="h-10 w-10 rounded-full bg-[#229ED9]/15 flex items-center justify-center shrink-0">
          <MessageCircle size={18} className="text-[#229ED9]" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium text-text-primary">Telegram</p>
          <p className="text-xs text-text-muted">Быстрый ответ в рабочее время</p>
        </div>
        <a
          href="https://t.me/skavellion_support"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-input bg-[#229ED9]/15 hover:bg-[#229ED9]/25 text-[#229ED9] px-3 py-1.5 text-sm font-medium transition-colors"
        >
          Написать
        </a>
      </div>

      {/* Contact form */}
      <div className="rounded-card bg-surface border border-border-neutral p-5">
        <h2 className="text-base font-semibold text-text-primary mb-4">Форма обращения</h2>

        {sent ? (
          <div className="py-6 text-center">
            <div className="h-12 w-12 rounded-full bg-emerald-500/15 flex items-center justify-center mx-auto mb-3">
              <Send size={20} className="text-emerald-400" />
            </div>
            <p className="text-sm text-text-primary font-medium mb-1">Сообщение отправлено</p>
            <p className="text-xs text-text-muted">Ответим в ближайшее время</p>
            <button
              onClick={() => setSent(false)}
              className="mt-4 text-xs text-accent hover:underline"
            >
              Отправить ещё
            </button>
          </div>
        ) : (
          <>
            <div className="mb-3">
              <label className="block text-xs text-text-muted mb-1">Имя</label>
              <input
                value={user?.display_name ?? ''}
                disabled
                className="w-full rounded-input bg-white/5 border border-border-neutral px-3 py-2 text-sm text-text-secondary"
              />
            </div>
            <div className="mb-4">
              <label className="block text-xs text-text-muted mb-1">Сообщение</label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={5}
                maxLength={2000}
                placeholder="Опишите вашу проблему или вопрос…"
                className="w-full rounded-input bg-white/5 border border-border-neutral px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/60 resize-none"
              />
              <p className="text-xs text-text-muted text-right mt-1">{message.length}/2000</p>
            </div>
            {mutation.isError && (
              <p className="mb-3 text-xs text-red-400">
                {mutation.error instanceof ApiError ? mutation.error.detail : 'Ошибка отправки'}
              </p>
            )}
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || !message.trim()}
              className="w-full rounded-input bg-accent hover:bg-accent-hover disabled:opacity-50 text-white font-medium py-2.5 text-sm transition-colors flex items-center justify-center gap-2"
            >
              {mutation.isPending ? (
                <><Loader2 size={14} className="animate-spin" /> Отправка…</>
              ) : (
                <><Send size={14} /> Отправить</>
              )}
            </button>
          </>
        )}
      </div>
    </div>
  )
}

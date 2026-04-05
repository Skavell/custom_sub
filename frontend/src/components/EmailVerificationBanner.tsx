import { useState, useRef } from 'react'
import { AlertTriangle, Send, CheckCircle } from 'lucide-react'
import { api, ApiError } from '@/lib/api'

interface Props {
  userEmail: string
}

export default function EmailVerificationBanner({ userEmail }: Props) {
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [cooldownLeft, setCooldownLeft] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const startCooldown = () => {
    setCooldownLeft(60)
    timerRef.current = setInterval(() => {
      setCooldownLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current!)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  const handleSend = async () => {
    if (status === 'sending' || cooldownLeft > 0) return
    setStatus('sending')
    setErrorMsg(null)
    try {
      await api.post('/api/auth/verify-email/send', {})
      setStatus('sent')
      startCooldown()
    } catch (e) {
      setStatus('error')
      setErrorMsg(e instanceof ApiError ? e.detail : 'Ошибка отправки. Попробуйте позже.')
    }
  }

  return (
    <div className="rounded-card border border-yellow-500/30 bg-yellow-500/5 px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
      <div className="flex items-start gap-2 flex-1 min-w-0">
        <AlertTriangle size={16} className="text-yellow-400 mt-0.5 shrink-0" />
        <div className="text-sm text-text-secondary min-w-0">
          <span className="text-text-primary font-medium">Подтвердите email</span>
          {' '}
          <span className="truncate">{userEmail}</span>
          {' '}— это необходимо для активации пробного периода.
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {status === 'sent' && (
          <span className="flex items-center gap-1 text-xs text-green-400">
            <CheckCircle size={13} />
            Письмо отправлено
          </span>
        )}
        {errorMsg && (
          <span className="text-xs text-red-400">{errorMsg}</span>
        )}
        <button
          onClick={handleSend}
          disabled={status === 'sending' || cooldownLeft > 0}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input text-xs font-medium bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Send size={12} />
          {cooldownLeft > 0
            ? `Повторить через ${cooldownLeft}с`
            : status === 'sending'
            ? 'Отправляем...'
            : 'Отправить письмо'}
        </button>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'

interface Props {
  hasMadePayment: boolean
  hasSubscription: boolean
  onActivateTrial: () => void
}

const LS_DISMISSED = 'onboarding_dismissed'
const LS_COMPLETED = 'onboarding_completed'
const LS_INSTALL_VISITED = 'install_visited'

export function OnboardingCard({ hasMadePayment, hasSubscription, onActivateTrial }: Props) {
  const navigate = useNavigate()
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(LS_DISMISSED) === 'true')
  const [completed, setCompleted] = useState(() => localStorage.getItem(LS_COMPLETED) === 'true')
  const [installVisited, setInstallVisited] = useState(() => localStorage.getItem(LS_INSTALL_VISITED) === 'true')
  const [celebrating, setCelebrating] = useState(false)

  const steps = [
    {
      label: 'Создать аккаунт',
      done: true,
      locked: false,
      action: null,
    },
    {
      label: 'Активировать пробный период',
      done: hasSubscription,
      locked: false,
      action: hasSubscription ? null : onActivateTrial,
    },
    {
      label: 'Установить приложение',
      done: installVisited && hasSubscription,
      locked: !hasSubscription,
      action: () => navigate('/install'),
    },
    {
      label: 'Продлить подписку',
      done: hasMadePayment,
      locked: !(installVisited && hasSubscription),
      action: () => navigate('/subscription'),
    },
  ]

  const allDone = steps.every(s => s.done)
  const currentStepIndex = steps.findIndex(s => !s.done && !s.locked)

  useEffect(() => {
    if (allDone && !completed) {
      setCelebrating(true)
      const t = setTimeout(() => {
        localStorage.setItem(LS_COMPLETED, 'true')
        setCompleted(true)
      }, 2000)
      return () => clearTimeout(t)
    }
  }, [allDone, completed])

  if (dismissed || completed) return null

  const handleDismiss = () => {
    localStorage.setItem(LS_DISMISSED, 'true')
    setDismissed(true)
  }

  if (celebrating) {
    return (
      <div className="rounded-card border border-green-500/40 bg-green-500/5 p-4 mb-4 flex flex-col items-center gap-2 text-center">
        <span className="text-2xl">🎉</span>
        <p className="text-sm font-semibold text-green-400">Всё настроено!</p>
      </div>
    )
  }

  return (
    <div className="rounded-card border border-accent/50 bg-accent/5 p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-accent">🚀 Начало работы</span>
        <button
          onClick={handleDismiss}
          className="text-text-muted hover:text-text-secondary transition-colors"
          aria-label="Скрыть"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex gap-1 mb-4">
        {steps.map((s, i) => (
          <div
            key={i}
            className={`flex-1 h-1 rounded-full transition-colors duration-300 ${
              s.done ? 'bg-green-500' : i === currentStepIndex ? 'bg-accent' : 'bg-border-neutral'
            }`}
          />
        ))}
      </div>

      <div className="flex flex-col gap-2">
        {steps.map((s, i) => {
          const isActive = i === currentStepIndex
          return (
            <button
              key={i}
              onClick={s.action && !s.locked ? s.action : undefined}
              disabled={s.locked || s.done || !s.action}
              className={`flex items-center gap-3 rounded-input px-3 py-2 text-sm transition-colors w-full text-left ${
                isActive
                  ? 'bg-accent/10 hover:bg-accent/20 cursor-pointer'
                  : 'cursor-default'
              } ${s.locked ? 'opacity-40' : ''}`}
            >
              <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                s.done
                  ? 'bg-green-500 text-white'
                  : isActive
                  ? 'bg-accent text-white'
                  : 'bg-border-neutral text-text-muted'
              }`}>
                {s.done ? '✓' : s.locked ? '🔒' : i + 1}
              </div>

              <span className={`flex-1 ${s.done ? 'line-through text-text-muted' : isActive ? 'text-text-primary font-medium' : 'text-text-secondary'}`}>
                {s.label}
              </span>

              {isActive && <span className="text-accent text-xs">→</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}

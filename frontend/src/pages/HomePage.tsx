import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient, useMutation, useQuery } from '@tanstack/react-query'
import { Shield, Zap, Download, RefreshCw, AlertCircle } from 'lucide-react'
import { useSubscription } from '@/hooks/useSubscription'
import { useAuth } from '@/hooks/useAuth'
import { api, ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { TrialActivateResponse, SubscriptionResponse, OAuthConfigResponse } from '@/types/api'
import EmailVerificationBanner from '@/components/EmailVerificationBanner'

function StatusBadge({ status }: { status: string }) {
  const colors = {
    active: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    expired: 'bg-red-500/15 text-red-400 border-red-500/20',
    disabled: 'bg-slate-500/15 text-slate-400 border-slate-500/20',
  }
  const labels = { active: 'Активна', expired: 'Истекла', disabled: 'Отключена' }
  return (
    <span className={cn('inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium', colors[status as keyof typeof colors] ?? colors.disabled)}>
      {labels[status as keyof typeof labels] ?? status}
    </span>
  )
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function TrialCard({ sub }: { sub: SubscriptionResponse }) {
  return (
    <div className="rounded-card bg-surface border border-border-neutral p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Тип подписки</p>
          <p className="text-text-primary font-semibold">Пробный период</p>
        </div>
        <StatusBadge status={sub.status} />
      </div>
      <div className="grid grid-cols-2 gap-4 mb-5 text-sm">
        <div>
          <p className="text-text-muted mb-0.5">Истекает</p>
          <p className="text-text-primary">{formatDate(sub.expires_at)}</p>
        </div>
        <div>
          <p className="text-text-muted mb-0.5">Осталось</p>
          <p className="text-text-primary">{sub.days_remaining} дн.</p>
        </div>
      </div>
      <div className="mb-5 p-3 rounded-input bg-white/5 flex items-center gap-2 text-sm text-text-secondary">
        <Zap size={14} className="text-accent shrink-0" />
        <span>Трафик: 30 ГБ (пробный лимит)</span>
      </div>
      <Link
        to="/subscription"
        className="block w-full text-center rounded-input bg-accent hover:bg-accent-hover text-white font-medium py-2.5 text-sm transition-colors"
      >
        Оформить подписку
      </Link>
    </div>
  )
}

function PaidCard({ sub }: { sub: SubscriptionResponse }) {
  return (
    <div className="rounded-card bg-surface border border-border-accent p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Тип подписки</p>
          <p className="text-text-primary font-semibold">Платная подписка</p>
        </div>
        <StatusBadge status={sub.status} />
      </div>
      <div className="grid grid-cols-2 gap-4 mb-5 text-sm">
        <div>
          <p className="text-text-muted mb-0.5">Истекает</p>
          <p className="text-text-primary">{formatDate(sub.expires_at)}</p>
        </div>
        <div>
          <p className="text-text-muted mb-0.5">Осталось</p>
          <p className="text-text-primary">{sub.days_remaining} дн.</p>
        </div>
      </div>
      <div className="mb-5 p-3 rounded-input bg-accent/10 flex items-center gap-2 text-sm text-accent">
        <Shield size={14} className="shrink-0" />
        <span>Безлимитный трафик</span>
      </div>
      <div className="flex gap-3">
        <Link
          to="/subscription"
          className="flex-1 text-center rounded-input border border-accent/40 text-accent hover:bg-accent/10 font-medium py-2.5 text-sm transition-colors"
        >
          Продлить
        </Link>
        <Link
          to="/install"
          className="flex-1 text-center rounded-input bg-accent hover:bg-accent-hover text-white font-medium py-2.5 text-sm transition-colors flex items-center justify-center gap-1.5"
        >
          <Download size={14} />
          Установить
        </Link>
      </div>
    </div>
  )
}

function ExpiredCard() {
  return (
    <div className="rounded-card bg-surface border border-red-500/20 p-6">
      <div className="flex items-start justify-between mb-4">
        <p className="text-text-primary font-semibold">Подписка</p>
        <StatusBadge status="expired" />
      </div>
      <div className="mb-5 p-3 rounded-input bg-red-500/10 flex items-center gap-2 text-sm text-red-400">
        <AlertCircle size={14} className="shrink-0" />
        <span>Срок подписки истёк. Продлите для восстановления доступа.</span>
      </div>
      <Link
        to="/subscription"
        className="block w-full text-center rounded-input bg-accent hover:bg-accent-hover text-white font-medium py-2.5 text-sm transition-colors"
      >
        Продлить подписку
      </Link>
    </div>
  )
}

function TrialCTA({ onActivate, isLoading, error, showVerifyBanner }: { onActivate: () => void; isLoading: boolean; error: string | null; showVerifyBanner: boolean }) {
  return (
    <div className="rounded-card bg-surface border border-border-accent p-6">
      <div className="mb-4">
        <div className="h-12 w-12 rounded-full bg-accent/15 flex items-center justify-center mb-4">
          <Shield size={24} className="text-accent" />
        </div>
        <h2 className="text-lg font-bold text-text-primary mb-2">Активировать пробный период</h2>
        <p className="text-sm text-text-secondary leading-relaxed">
          30 ГБ трафика, 3 дня. Платная подписка — безлимит.
        </p>
      </div>
      {error && (
        <div className="mb-4 p-3 rounded-input bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          {error}
        </div>
      )}
      <button
        onClick={onActivate}
        disabled={isLoading || showVerifyBanner}
        title={showVerifyBanner ? 'Сначала подтвердите email' : undefined}
        className={`w-full rounded-input bg-accent hover:bg-accent-hover disabled:opacity-50 text-white font-medium py-2.5 text-sm transition-colors flex items-center justify-center gap-2 ${showVerifyBanner ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        {isLoading ? (
          <><RefreshCw size={14} className="animate-spin" /> Активация…</>
        ) : (
          'Активировать бесплатно'
        )}
      </button>
    </div>
  )
}

export default function HomePage() {
  const queryClient = useQueryClient()
  const { data: sub, isLoading } = useSubscription()
  const { user } = useAuth()
  const { data: oauthConfig } = useQuery<OAuthConfigResponse>({
    queryKey: ['oauthConfig'],
    queryFn: () => api.get<OAuthConfigResponse>('/api/auth/oauth-config'),
    staleTime: 300_000,
  })
  const [trialError, setTrialError] = useState<string | null>(null)

  const showVerifyBanner =
    user?.email_verified === false &&
    oauthConfig?.email_verification_required === true

  const emailProvider = user?.providers.find(p => p.type === 'email')

  const trialMutation = useMutation({
    mutationFn: () => api.post<TrialActivateResponse>('/api/subscriptions/trial'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription'] })
      setTrialError(null)
    },
    onError: (e) => {
      if (e instanceof ApiError) setTrialError(e.detail)
      else setTrialError('Произошла ошибка. Попробуйте позже.')
    },
  })

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[40vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 max-w-xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Главная</h1>

      {showVerifyBanner && emailProvider?.identifier && (
        <EmailVerificationBanner userEmail={emailProvider.identifier} />
      )}

      {/* Subscription block */}
      {sub === null || sub === undefined ? (
        <TrialCTA
          onActivate={() => trialMutation.mutate()}
          isLoading={trialMutation.isPending}
          error={trialError}
          showVerifyBanner={showVerifyBanner ?? false}
        />
      ) : sub.status === 'active' && sub.type === 'trial' ? (
        <TrialCard sub={sub} />
      ) : sub.status === 'active' && sub.type === 'paid' ? (
        <PaidCard sub={sub} />
      ) : (
        <ExpiredCard />
      )}

      {/* Quick links */}
      <div className="mt-6 grid grid-cols-3 gap-3">
        {[
          { to: '/install', icon: Download, label: 'Установка' },
          { to: '/subscription', icon: Zap, label: 'Тарифы' },
          { to: '/support', icon: Shield, label: 'Поддержка' },
        ].map(({ to, icon: Icon, label }) => (
          <Link
            key={to}
            to={to}
            className="flex flex-col items-center gap-2 rounded-card bg-surface border border-border-neutral p-4 text-text-secondary hover:text-text-primary hover:border-accent/30 transition-colors"
          >
            <Icon size={20} />
            <span className="text-xs">{label}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}

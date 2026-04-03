import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Check, Tag, Loader2 } from 'lucide-react'
import { usePlans } from '@/hooks/usePlans'
import { useSubscription } from '@/hooks/useSubscription'
import { api, ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import type {
  Plan,
  ValidatePromoResponse,
  PaymentResponse,
  ApplyPromoRequest,
  CreatePaymentRequest,
} from '@/types/api'

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function addDays(isoDate: string, days: number) {
  const d = new Date(isoDate)
  d.setDate(d.getDate() + days)
  return d.toISOString()
}

function pricePerMonth(plan: Plan): number {
  return Math.round((plan.price_rub / plan.duration_days) * 30)
}

function PlanCard({
  plan,
  selected,
  onSelect,
  isNewUser,
}: {
  plan: Plan
  selected: boolean
  onSelect: () => void
  isNewUser: boolean
}) {
  const showNewUserPrice = isNewUser && plan.name === '1_month' && plan.new_user_price_rub != null

  return (
    <button
      onClick={onSelect}
      className={cn(
        'relative w-full rounded-card border p-4 text-left transition-all',
        selected
          ? 'border-accent bg-accent/10'
          : 'border-border-neutral bg-surface hover:border-accent/40',
      )}
    >
      {selected && (
        <div className="absolute top-3 right-3 h-5 w-5 rounded-full bg-accent flex items-center justify-center">
          <Check size={12} className="text-white" />
        </div>
      )}
      <p className="font-semibold text-text-primary mb-1">{plan.label}</p>
      <div className="flex items-baseline gap-2">
        <span className="text-xl font-bold text-accent">
          {showNewUserPrice ? plan.new_user_price_rub : plan.price_rub}₽
        </span>
        {showNewUserPrice && (
          <span className="text-sm text-text-muted line-through">{plan.price_rub}₽</span>
        )}
      </div>
      <p className="text-xs text-text-muted mt-1">{pricePerMonth(plan)}₽/мес</p>
      {showNewUserPrice && (
        <span className="mt-2 inline-block text-[10px] bg-emerald-500/15 text-emerald-400 rounded-full px-2 py-0.5">
          Скидка для новых
        </span>
      )}
    </button>
  )
}

export default function SubscriptionPage() {
  const { data: plans = [], isLoading: plansLoading } = usePlans()
  const { data: sub } = useSubscription()

  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const [promoInput, setPromoInput] = useState('')
  const [validatedPromo, setValidatedPromo] = useState<ValidatePromoResponse | null>(null)
  const [promoError, setPromoError] = useState<string | null>(null)
  const [promoValidating, setPromoValidating] = useState(false)

  const [bonusPromoInput, setBonusPromoInput] = useState('')
  const [bonusResult, setBonusResult] = useState<string | null>(null)
  const [bonusError, setBonusError] = useState<string | null>(null)

  const selectedPlan = plans.find((p) => p.id === selectedPlanId) ?? null
  const isNewUser = sub === null || sub === undefined

  const basePrice = selectedPlan?.price_rub ?? 0
  const newUserPrice =
    isNewUser && selectedPlan?.name === '1_month' && selectedPlan.new_user_price_rub != null
      ? selectedPlan.new_user_price_rub
      : null
  const discountPrice =
    validatedPromo?.type === 'discount_percent'
      ? Math.round(basePrice * (1 - validatedPromo.value / 100))
      : null
  const finalPrice = Math.min(
    basePrice,
    newUserPrice ?? Infinity,
    discountPrice ?? Infinity,
  )

  const bonusDays = validatedPromo?.type === 'bonus_days' ? validatedPromo.value : 0
  const projectedExpiry = selectedPlan
    ? addDays(
        sub?.expires_at ?? new Date().toISOString(),
        selectedPlan.duration_days + bonusDays,
      )
    : null

  async function handleValidatePromo() {
    if (!promoInput.trim()) return
    setPromoValidating(true)
    setPromoError(null)
    setValidatedPromo(null)
    try {
      const result = await api.get<ValidatePromoResponse>(
        `/api/promo-codes/validate/${encodeURIComponent(promoInput.trim().toUpperCase())}`,
      )
      if (result.already_used) {
        setPromoError('Этот промокод уже использован вами')
      } else {
        setValidatedPromo(result)
      }
    } catch (e) {
      if (e instanceof ApiError) setPromoError(e.detail)
      else setPromoError('Промокод не найден')
    } finally {
      setPromoValidating(false)
    }
  }

  const payMutation = useMutation({
    mutationFn: (req: CreatePaymentRequest) =>
      api.post<PaymentResponse>('/api/payments', req),
    onSuccess: (data) => {
      window.location.href = data.payment_url
    },
  })

  const applyBonusMutation = useMutation({
    mutationFn: (req: ApplyPromoRequest) =>
      api.post('/api/promo-codes/apply', req),
    onSuccess: (data: unknown) => {
      const d = data as { days_added: number; new_expires_at: string }
      setBonusResult(`Готово! Добавлено ${d.days_added} дней. Новый срок: ${formatDate(d.new_expires_at)}`)
      setBonusError(null)
      setBonusPromoInput('')
    },
    onError: (e) => {
      setBonusError(e instanceof ApiError ? e.detail : 'Ошибка применения промокода')
    },
  })

  function handlePay() {
    if (!selectedPlanId) return
    payMutation.mutate({
      plan_id: selectedPlanId,
      promo_code: validatedPromo?.code ?? null,
    })
  }

  if (plansLoading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[40vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  const activePlans = [...plans].sort((a, b) => a.sort_order - b.sort_order)

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-1">Подписка</h1>
      {sub?.status === 'active' && (
        <p className="text-sm text-text-muted mb-5">
          Активна до {formatDate(sub.expires_at)} · {sub.days_remaining} дн. осталось
        </p>
      )}
      {!sub && (
        <p className="text-sm text-emerald-400 mb-5">Скидка для новых пользователей на 1 месяц</p>
      )}

      {/* Plan grid */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        {activePlans.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            selected={plan.id === selectedPlanId}
            onSelect={() => setSelectedPlanId(plan.id)}
            isNewUser={isNewUser}
          />
        ))}
      </div>

      {/* Promo code */}
      <div className="rounded-card bg-surface border border-border-neutral p-4 mb-4">
        <p className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
          <Tag size={14} className="text-accent" /> Промокод
        </p>
        <div className="flex gap-2">
          <input
            value={promoInput}
            onChange={(e) => {
              setPromoInput(e.target.value.toUpperCase())
              setValidatedPromo(null)
              setPromoError(null)
            }}
            placeholder="PROMO2025"
            className="flex-1 rounded-input bg-white/5 border border-border-neutral px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/60"
          />
          <button
            onClick={handleValidatePromo}
            disabled={promoValidating || !promoInput.trim()}
            className="rounded-input bg-accent/10 hover:bg-accent/20 text-accent px-4 text-sm font-medium transition-colors disabled:opacity-50"
          >
            {promoValidating ? <Loader2 size={14} className="animate-spin" /> : 'Проверить'}
          </button>
        </div>
        {promoError && <p className="mt-2 text-xs text-red-400">{promoError}</p>}
        {validatedPromo && (
          <p className="mt-2 text-xs text-emerald-400">
            {validatedPromo.type === 'discount_percent'
              ? `Скидка ${validatedPromo.value}% применена`
              : `Бонус ${validatedPromo.value} дней после оплаты`}
          </p>
        )}
      </div>

      {/* Order summary + pay */}
      {selectedPlan && (
        <div className="rounded-card bg-surface border border-accent/20 p-4 mb-4">
          <p className="text-sm font-medium text-text-primary mb-3">Итого</p>
          <div className="space-y-2 text-sm text-text-secondary mb-4">
            <div className="flex justify-between">
              <span>Тариф</span>
              <span className="text-text-primary">{selectedPlan.label}</span>
            </div>
            {finalPrice !== basePrice && (
              <div className="flex justify-between">
                <span>Цена без скидки</span>
                <span className="line-through text-text-muted">{basePrice}₽</span>
              </div>
            )}
            <div className="flex justify-between font-semibold text-text-primary">
              <span>К оплате</span>
              <span className="text-accent">{finalPrice}₽</span>
            </div>
            {projectedExpiry && (
              <div className="flex justify-between">
                <span>Подписка до</span>
                <span className="text-text-primary">{formatDate(projectedExpiry)}</span>
              </div>
            )}
            {bonusDays > 0 && (
              <div className="flex justify-between text-emerald-400">
                <span>Бонус</span>
                <span>+{bonusDays} дн.</span>
              </div>
            )}
          </div>
          <p className="text-xs text-text-muted mb-3">Подписка продлится, а не начнётся заново</p>
          {payMutation.isError && (
            <p className="mb-3 text-xs text-red-400">
              {payMutation.error instanceof ApiError ? payMutation.error.detail : 'Ошибка оплаты'}
            </p>
          )}
          <button
            onClick={handlePay}
            disabled={payMutation.isPending}
            className="w-full rounded-input bg-accent hover:bg-accent-hover disabled:opacity-50 text-white font-medium py-2.5 text-sm transition-colors flex items-center justify-center gap-2"
          >
            {payMutation.isPending ? (
              <><Loader2 size={14} className="animate-spin" /> Подготовка…</>
            ) : (
              'Оплатить криптовалютой'
            )}
          </button>
        </div>
      )}

      {/* Standalone bonus apply */}
      <div className="rounded-card bg-surface border border-border-neutral p-4">
        <p className="text-sm font-medium text-text-primary mb-1">Активировать промокод без оплаты</p>
        <p className="text-xs text-text-muted mb-3">Только для промокодов типа «бонусные дни»</p>
        <div className="flex gap-2">
          <input
            value={bonusPromoInput}
            onChange={(e) => {
              setBonusPromoInput(e.target.value.toUpperCase())
              setBonusResult(null)
              setBonusError(null)
            }}
            placeholder="BONUS2025"
            className="flex-1 rounded-input bg-white/5 border border-border-neutral px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/60"
          />
          <button
            onClick={() => applyBonusMutation.mutate({ code: bonusPromoInput.trim() })}
            disabled={applyBonusMutation.isPending || !bonusPromoInput.trim()}
            className="rounded-input bg-white/5 hover:bg-white/10 text-text-secondary px-4 text-sm transition-colors disabled:opacity-50"
          >
            {applyBonusMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : 'Применить'}
          </button>
        </div>
        {bonusError && <p className="mt-2 text-xs text-red-400">{bonusError}</p>}
        {bonusResult && <p className="mt-2 text-xs text-emerald-400">{bonusResult}</p>}
      </div>
    </div>
  )
}

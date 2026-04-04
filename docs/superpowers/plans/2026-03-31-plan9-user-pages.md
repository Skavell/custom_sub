# Plan 9: User Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build all 6 user-facing pages (Home, Subscription, Install, Docs, Support, Profile) as fully functional React components consuming the existing backend API.

**Architecture:** Each page is a self-contained component in `src/pages/`. Data fetching via TanStack Query hooks in `src/hooks/`. The backend API is already fully built — this plan only touches the frontend. No global state store — each page fetches what it needs via `useQuery`/`useMutation`. Mutations call `queryClient.invalidateQueries` to refresh related data after writes.

**Tech Stack:** React 18, TanStack Query v5, React Router v6, Tailwind CSS 3, lucide-react, react-markdown + remark-gfm (markdown rendering)

---

## Known API Endpoints (all require auth cookie)

| Method | Path | Returns | Used by |
|--------|------|---------|---------|
| GET | `/api/subscriptions/me` | `SubscriptionResponse \| null` | Home, Subscription |
| POST | `/api/subscriptions/trial` | `{subscription, message}` | Home |
| GET | `/api/plans` | `PlanResponse[]` | Subscription |
| GET | `/api/promo-codes/validate/{code}` | `ValidatePromoResponse` | Subscription |
| POST | `/api/promo-codes/apply` | `{days_added, new_expires_at}` | Subscription |
| POST | `/api/payments` | `PaymentResponse` | Subscription |
| GET | `/api/payments/history` | `TransactionHistoryItem[]` | Profile |
| GET | `/api/install/subscription-link` | `{subscription_url}` | Install |
| GET | `/api/articles` | `ArticleListItem[]` | Docs |
| GET | `/api/articles/{slug}` | `ArticleDetail` | Docs |
| POST | `/api/support/message` | 200 OK | Support |
| DELETE | `/api/users/me/providers/{provider}` | 204 No Content | Profile |

## SubscriptionResponse shape (from backend)
```typescript
{
  type: 'trial' | 'paid'
  status: 'active' | 'expired' | 'disabled'
  started_at: string
  expires_at: string
  traffic_limit_gb: number | null  // null = unlimited; 30 for trial
  days_remaining: number
}
```

## PaymentResponse shape
```typescript
{
  payment_url: string
  transaction_id: string
  amount_rub: number
  amount_usdt: string
  is_existing: boolean
}
```

## TransactionHistoryItem shape
```typescript
{
  id: string
  type: string             // trial_activation | payment | promo_bonus | manual
  status: string           // pending | completed | failed
  amount_rub: number | null
  plan_name: string | null
  days_added: number | null
  created_at: string
  completed_at: string | null
}
```

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Modify** | `frontend/package.json` | Add react-markdown, remark-gfm |
| **Create** | `frontend/src/hooks/usePlans.ts` | `useQuery` for `/api/plans` |
| **Create** | `frontend/src/hooks/useTransactions.ts` | `useQuery` for `/api/payments/history` |
| **Replace** | `frontend/src/pages/HomePage.tsx` | Subscription state hub, trial CTA |
| **Create** | `frontend/src/pages/SubscriptionPage.tsx` | Plan selector, promo, payment redirect |
| **Create** | `frontend/src/pages/InstallPage.tsx` | OS detection, deep links, steps |
| **Create** | `frontend/src/pages/DocsPage.tsx` | Article list |
| **Create** | `frontend/src/pages/DocsArticlePage.tsx` | Markdown article detail |
| **Create** | `frontend/src/pages/SupportPage.tsx` | Contact form, Telegram link |
| **Create** | `frontend/src/pages/ProfilePage.tsx` | Account info, providers, transactions |
| **Modify** | `frontend/src/App.tsx` | Add all new routes |
| **Modify** | `frontend/src/types/api.ts` | Add missing types |

---

## Task 1: Dependencies + Shared Hooks

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/hooks/usePlans.ts`
- Create: `frontend/src/hooks/useTransactions.ts`
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add react-markdown + remark-gfm to package.json**

In `frontend/package.json`, add to `"dependencies"`:
```json
"react-markdown": "^9.0.1",
"remark-gfm": "^4.0.0"
```

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm install`
Expected: installs without errors

- [ ] **Step 2: Extend src/types/api.ts with missing types**

Append to `frontend/src/types/api.ts`:
```typescript
// Added in Plan 9

export interface SubscriptionResponse {
  type: 'trial' | 'paid'
  status: 'active' | 'expired' | 'disabled'
  started_at: string
  expires_at: string
  traffic_limit_gb: number | null
  days_remaining: number
}

export interface TrialActivateResponse {
  subscription: SubscriptionResponse
  message: string
}

export interface PaymentResponse {
  payment_url: string
  transaction_id: string
  amount_rub: number
  amount_usdt: string
  is_existing: boolean
}

export interface TransactionHistoryItem {
  id: string
  type: string
  status: string
  amount_rub: number | null
  plan_name: string | null
  days_added: number | null
  created_at: string
  completed_at: string | null
}

export interface ArticleListItem {
  id: string
  slug: string
  title: string
  preview_image_url: string | null
  sort_order: number
  created_at: string
}

export interface ArticleDetailResponse extends ArticleListItem {
  content: string
  updated_at: string
}

export interface ApplyPromoRequest {
  code: string
}

export interface CreatePaymentRequest {
  plan_id: string
  promo_code?: string | null
}
```

- [ ] **Step 3: Create src/hooks/usePlans.ts**

```typescript
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Plan } from '@/types/api'

export function usePlans() {
  return useQuery<Plan[]>({
    queryKey: ['plans'],
    queryFn: () => api.get<Plan[]>('/api/plans'),
    staleTime: 5 * 60_000,
  })
}
```

- [ ] **Step 4: Create src/hooks/useTransactions.ts**

```typescript
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { TransactionHistoryItem } from '@/types/api'

export function useTransactions() {
  return useQuery<TransactionHistoryItem[]>({
    queryKey: ['transactions'],
    queryFn: () => api.get<TransactionHistoryItem[]>('/api/payments/history'),
    staleTime: 30_000,
  })
}
```

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run type-check 2>&1 | head -20`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/package.json frontend/package-lock.json frontend/src/types/api.ts frontend/src/hooks/usePlans.ts frontend/src/hooks/useTransactions.ts
git commit -m "feat: add plan/transaction hooks and extend API types"
```

---

## Task 2: Home Page

**Files:**
- Replace: `frontend/src/pages/HomePage.tsx`

The Home page shows subscription state-based content:
- **No subscription (`null`):** CTA card to activate trial (30 ГБ, 3 дня)
- **Trial active:** expiry, days remaining, traffic limit badge, "Оформить подписку" button
- **Paid active:** expiry, days remaining, "Безлимит" badge, "Продлить" + "Установка" buttons
- **Expired:** red status, "Продлить подписку" button

Trial activation: `POST /api/subscriptions/trial` → on success invalidate `['subscription']` query.

- [ ] **Step 1: Create HomePage.tsx**

```tsx
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { Shield, Zap, Download, RefreshCw, AlertCircle } from 'lucide-react'
import { useSubscription } from '@/hooks/useSubscription'
import { api, ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { TrialActivateResponse, SubscriptionResponse } from '@/types/api'

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

function TrialCTA({ onActivate, isLoading, error }: { onActivate: () => void; isLoading: boolean; error: string | null }) {
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
        disabled={isLoading}
        className="w-full rounded-input bg-accent hover:bg-accent-hover disabled:opacity-50 text-white font-medium py-2.5 text-sm transition-colors flex items-center justify-center gap-2"
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
  const [trialError, setTrialError] = useState<string | null>(null)

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

      {/* Subscription block */}
      {sub === null || sub === undefined ? (
        <TrialCTA
          onActivate={() => trialMutation.mutate()}
          isLoading={trialMutation.isPending}
          error={trialError}
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
```

- [ ] **Step 2: Type-check**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run type-check 2>&1 | head -30`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/src/pages/HomePage.tsx
git commit -m "feat: implement Home page with subscription state display and trial CTA"
```

---

## Task 3: Subscription Page

**Files:**
- Create: `frontend/src/pages/SubscriptionPage.tsx`

Logic:
1. Fetch plans via `usePlans()`, subscription via `useSubscription()`
2. User clicks a plan → it becomes selected
3. Promo code field: "Проверить" button → `GET /api/promo-codes/validate/{code}`
   - `discount_percent`: show discounted price in order summary
   - `bonus_days`: show "+ X бонусных дней" note
   - `already_used`: show error
4. New user discount: if `subscription === null` and selected plan is 1-month and plan has `new_user_price_rub` — show discounted price automatically
5. "Оплатить" → `POST /api/payments {plan_id, promo_code?}` → `window.location.href = payment_url`
6. Standalone bonus apply section: separate promo input → `POST /api/promo-codes/apply {code}`

- [ ] **Step 1: Create SubscriptionPage.tsx**

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
  ApplyPromoResponse,
  CreatePaymentRequest,
  ApplyPromoRequest,
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
  const navigate = useNavigate()
  const { data: plans = [], isLoading: plansLoading } = usePlans()
  const { data: sub } = useSubscription()

  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const [promoInput, setPromoInput] = useState('')
  const [validatedPromo, setValidatedPromo] = useState<ValidatePromoResponse | null>(null)
  const [promoError, setPromoError] = useState<string | null>(null)
  const [promoValidating, setPromoValidating] = useState(false)

  // Standalone bonus apply state
  const [bonusPromoInput, setBonusPromoInput] = useState('')
  const [bonusResult, setBonusResult] = useState<string | null>(null)
  const [bonusError, setBonusError] = useState<string | null>(null)

  const selectedPlan = plans.find((p) => p.id === selectedPlanId) ?? null
  const isNewUser = sub === null || sub === undefined

  // Compute final price
  const basePrice = selectedPlan?.price_rub ?? 0
  const newUserPrice =
    isNewUser && selectedPlan?.name === '1_month' && selectedPlan.new_user_price_rub != null
      ? selectedPlan.new_user_price_rub
      : null
  const discountPrice =
    validatedPromo?.type === 'discount_percent'
      ? Math.round(basePrice * (1 - validatedPromo.value / 100))
      : null
  const finalPrice = (() => {
    const candidates = [basePrice]
    if (newUserPrice != null) candidates.push(newUserPrice)
    if (discountPrice != null) candidates.push(discountPrice)
    return Math.min(...candidates)
  })()

  const bonusDays = validatedPromo?.type === 'bonus_days' ? validatedPromo.value : 0
  const projectedExpiry = selectedPlan && sub
    ? addDays(sub.expires_at, selectedPlan.duration_days + bonusDays)
    : selectedPlan
    ? addDays(new Date().toISOString(), selectedPlan.duration_days + bonusDays)
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
      api.post<ApplyPromoResponse>('/api/promo-codes/apply', req),
    onSuccess: (data) => {
      setBonusResult(`Готово! Добавлено ${data.days_added} дней. Новый срок: ${formatDate(data.new_expires_at)}`)
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

  const activePlans = plans.filter((p) => p.sort_order >= 0).sort((a, b) => a.sort_order - b.sort_order)

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

      {/* Order summary + pay button */}
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
          <p className="text-xs text-text-muted mb-3">
            Подписка продлится, а не начнётся заново
          </p>
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
        <p className="text-sm font-medium text-text-primary mb-3">Активировать промокод без оплаты</p>
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
```

- [ ] **Step 2: Type-check**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run type-check 2>&1 | head -30`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/src/pages/SubscriptionPage.tsx
git commit -m "feat: implement Subscription page with plan selection, promo codes, and payment redirect"
```

---

## Task 4: Install Page

**Files:**
- Create: `frontend/src/pages/InstallPage.tsx`

Logic:
- `GET /api/install/subscription-link` → `{subscription_url}` — returns 403 if expired
- Detect OS from `navigator.userAgent`
- Manual OS switcher (5 tabs)
- Deep links per app as per spec
- If 403 → show "Подпишитесь для доступа" prompt

OS → apps mapping:
```
android: [FlClash (primary), Clash Meta]
ios:     [Clash Mi (primary)]
windows: [Clash Verge (primary), FlClash]
macos:   [FlClash (primary), Clash Verge]
linux:   [Clash Verge (primary)]
```

Deep link templates:
```
flclash:    flclash://install-config?url={SUB_LINK}
clash_mi:   clash://install-config?overwrite=no&name={DISPLAY_NAME}&url={SUB_LINK}
clash_meta: clashmeta://install-config?name={DISPLAY_NAME}&url={SUB_LINK}
clash_verge: clash://install-config?url={SUB_LINK}
```

- [ ] **Step 1: Create InstallPage.tsx**

```tsx
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Smartphone, Monitor, Apple, Terminal, ExternalLink, Copy, Check } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import type { InstallLinkResponse } from '@/types/api'

type OS = 'android' | 'ios' | 'windows' | 'macos' | 'linux'

function detectOS(): OS {
  const ua = navigator.userAgent.toLowerCase()
  if (/android/.test(ua)) return 'android'
  if (/iphone|ipad|ipod/.test(ua)) return 'ios'
  if (/win/.test(ua)) return 'windows'
  if (/mac/.test(ua)) return 'macos'
  return 'linux'
}

const OS_TABS: { id: OS; label: string; icon: React.FC<{ size?: number; className?: string }> }[] = [
  { id: 'android', label: 'Android', icon: Smartphone },
  { id: 'ios', label: 'iOS', icon: Apple },
  { id: 'windows', label: 'Windows', icon: Monitor },
  { id: 'macos', label: 'macOS', icon: Apple },
  { id: 'linux', label: 'Linux', icon: Terminal },
]

interface AppInfo {
  name: string
  deepLinkTemplate: (sub: string, name: string) => string
  storeUrl: string
  steps: string[]
}

const APPS: Record<string, AppInfo> = {
  flclash: {
    name: 'FlClash',
    deepLinkTemplate: (sub) => `flclash://install-config?url=${encodeURIComponent(sub)}`,
    storeUrl: 'https://github.com/chen08209/FlClash/releases/latest',
    steps: [
      'Установите FlClash',
      'Нажмите кнопку ниже для автоматической настройки',
      'Разрешите добавление профиля в приложении',
      'Включите туннель',
    ],
  },
  clash_mi: {
    name: 'Clash Mi',
    deepLinkTemplate: (sub, name) =>
      `clash://install-config?overwrite=no&name=${encodeURIComponent(name)}&url=${encodeURIComponent(sub)}`,
    storeUrl: 'https://apps.apple.com/app/clash-mi/id1574653991',
    steps: [
      'Установите Clash Mi из App Store',
      'Нажмите кнопку ниже для автоматической настройки',
      'Подтвердите добавление VPN-профиля',
      'Включите туннель',
    ],
  },
  clash_meta: {
    name: 'Clash Meta',
    deepLinkTemplate: (sub, name) =>
      `clashmeta://install-config?name=${encodeURIComponent(name)}&url=${encodeURIComponent(sub)}`,
    storeUrl: 'https://github.com/MetaCubeX/ClashMetaForAndroid/releases/latest',
    steps: [
      'Установите Clash Meta',
      'Нажмите кнопку ниже для автоматической настройки',
      'Разрешите добавление профиля',
      'Включите туннель',
    ],
  },
  clash_verge: {
    name: 'Clash Verge Rev',
    deepLinkTemplate: (sub) => `clash://install-config?url=${encodeURIComponent(sub)}`,
    storeUrl: 'https://github.com/clash-verge-rev/clash-verge-rev/releases/latest',
    steps: [
      'Установите Clash Verge Rev',
      'Нажмите кнопку ниже для автоматической настройки',
      'Подтвердите импорт профиля',
      'Включите системный прокси',
    ],
  },
}

const OS_APPS: Record<OS, string[]> = {
  android: ['flclash', 'clash_meta'],
  ios: ['clash_mi'],
  windows: ['clash_verge', 'flclash'],
  macos: ['flclash', 'clash_verge'],
  linux: ['clash_verge'],
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? 'Скопировано' : 'Скопировать'}
    </button>
  )
}

export default function InstallPage() {
  const { user } = useAuth()
  const [activeOS, setActiveOS] = useState<OS>(detectOS)
  const [activeApp, setActiveApp] = useState<string | null>(null)

  const { data: installData, isLoading, error } = useQuery<InstallLinkResponse>({
    queryKey: ['subscriptionLink'],
    queryFn: () => api.get<InstallLinkResponse>('/api/install/subscription-link'),
    retry: false,
    staleTime: 60_000,
  })

  const is403 = error instanceof ApiError && error.status === 403
  const appsForOS = OS_APPS[activeOS]
  const currentAppKey = activeApp ?? appsForOS[0]
  const app = APPS[currentAppKey]
  const subLink = installData?.subscription_url ?? ''
  const displayName = user?.display_name ?? 'Skavellion'

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-1">Установка</h1>
      <p className="text-sm text-text-muted mb-5">Настройте туннель на вашем устройстве</p>

      {is403 && (
        <div className="rounded-card bg-red-500/10 border border-red-500/20 p-5 mb-5">
          <p className="text-sm text-red-400 mb-3">Подписка истекла. Продлите для доступа к ссылке.</p>
          <Link
            to="/subscription"
            className="inline-block rounded-input bg-accent hover:bg-accent-hover text-white text-sm font-medium px-4 py-2 transition-colors"
          >
            Продлить подписку
          </Link>
        </div>
      )}

      {isLoading && (
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent mb-5" />
      )}

      {/* OS tabs */}
      <div className="flex gap-1 bg-surface border border-border-neutral rounded-card p-1 mb-5 overflow-x-auto">
        {OS_TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => { setActiveOS(id); setActiveApp(null) }}
            className={cn(
              'flex items-center gap-1.5 rounded-input px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors',
              activeOS === id
                ? 'bg-accent/15 text-accent'
                : 'text-text-muted hover:text-text-secondary',
            )}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </div>

      {/* App selector (only show if multiple apps) */}
      {appsForOS.length > 1 && (
        <div className="flex gap-2 mb-5">
          {appsForOS.map((key) => (
            <button
              key={key}
              onClick={() => setActiveApp(key)}
              className={cn(
                'rounded-input border px-3 py-1.5 text-xs font-medium transition-colors',
                currentAppKey === key
                  ? 'border-accent text-accent bg-accent/10'
                  : 'border-border-neutral text-text-secondary hover:border-accent/40',
              )}
            >
              {APPS[key].name}
            </button>
          ))}
        </div>
      )}

      {/* Install steps */}
      <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
        <h2 className="text-base font-semibold text-text-primary mb-4">{app.name}</h2>
        <ol className="space-y-4">
          {app.steps.map((step, i) => (
            <li key={i} className="flex gap-3">
              <span className="h-6 w-6 rounded-full bg-accent/15 text-accent text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                {i + 1}
              </span>
              <span className="text-sm text-text-secondary">{step}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Deep link button */}
      {subLink && (
        <a
          href={app.deepLinkTemplate(subLink, displayName)}
          className="block w-full text-center rounded-input bg-accent hover:bg-accent-hover text-white font-medium py-3 text-sm transition-colors mb-4"
        >
          <ExternalLink size={14} className="inline mr-1.5" />
          Открыть в {app.name}
        </a>
      )}

      {/* Manual fallback */}
      {subLink && (
        <div className="rounded-card bg-surface border border-border-neutral p-4">
          <p className="text-xs text-text-muted mb-2">Или вставьте ссылку вручную:</p>
          <div className="flex items-center gap-2 bg-white/5 rounded-input p-3">
            <code className="flex-1 text-xs text-text-secondary break-all">{subLink}</code>
            <CopyButton text={subLink} />
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Type-check**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run type-check 2>&1 | head -30`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/src/pages/InstallPage.tsx
git commit -m "feat: implement Install page with OS detection and deep links"
```

---

## Task 5: Docs Pages

**Files:**
- Create: `frontend/src/pages/DocsPage.tsx`
- Create: `frontend/src/pages/DocsArticlePage.tsx`

Note: `react-markdown` was installed in Task 1.

- [ ] **Step 1: Create DocsPage.tsx (article list)**

```tsx
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import type { ArticleListItem } from '@/types/api'

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

export default function DocsPage() {
  const { data: articles = [], isLoading } = useQuery<ArticleListItem[]>({
    queryKey: ['articles'],
    queryFn: () => api.get<ArticleListItem[]>('/api/articles'),
    staleTime: 5 * 60_000,
  })

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-1">Документация</h1>
      <p className="text-sm text-text-muted mb-5">Руководства и инструкции</p>

      {isLoading ? (
        <div className="flex justify-center py-10">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      ) : articles.length === 0 ? (
        <div className="rounded-card bg-surface border border-border-neutral p-8 text-center">
          <BookOpen size={32} className="mx-auto text-text-muted mb-3" />
          <p className="text-sm text-text-muted">Статьи появятся здесь</p>
        </div>
      ) : (
        <div className="space-y-3">
          {articles.map((article) => (
            <Link
              key={article.id}
              to={`/docs/${article.slug}`}
              className="group flex items-center gap-4 rounded-card bg-surface border border-border-neutral p-4 hover:border-accent/40 transition-colors"
            >
              {article.preview_image_url ? (
                <img
                  src={article.preview_image_url}
                  alt=""
                  className="h-14 w-20 rounded-input object-cover shrink-0"
                />
              ) : (
                <div className="h-14 w-20 rounded-input bg-accent/10 flex items-center justify-center shrink-0">
                  <BookOpen size={20} className="text-accent" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-text-primary group-hover:text-accent transition-colors truncate">
                  {article.title}
                </p>
                <p className="text-xs text-text-muted mt-0.5">{formatDate(article.created_at)}</p>
              </div>
              <ChevronRight size={16} className="text-text-muted shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create DocsArticlePage.tsx (markdown article)**

```tsx
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api, ApiError } from '@/lib/api'
import type { ArticleDetailResponse } from '@/types/api'

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

export default function DocsArticlePage() {
  const { slug } = useParams<{ slug: string }>()

  const { data: article, isLoading, error } = useQuery<ArticleDetailResponse>({
    queryKey: ['article', slug],
    queryFn: () => api.get<ArticleDetailResponse>(`/api/articles/${slug}`),
    enabled: !!slug,
    retry: false,
  })

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <Link
        to="/docs"
        className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary mb-5 transition-colors"
      >
        <ArrowLeft size={14} />
        Назад
      </Link>

      {isLoading && (
        <div className="flex justify-center py-10">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-card bg-red-500/10 border border-red-500/20 p-5 text-sm text-red-400">
          {error instanceof ApiError && error.status === 404
            ? 'Статья не найдена'
            : 'Ошибка загрузки статьи'}
        </div>
      )}

      {article && (
        <>
          <h1 className="text-2xl font-bold text-text-primary mb-2">{article.title}</h1>
          <p className="text-xs text-text-muted mb-6">Обновлено {formatDate(article.updated_at)}</p>
          <div className="prose prose-invert prose-sm max-w-none
            prose-headings:text-text-primary
            prose-p:text-text-secondary
            prose-a:text-accent prose-a:no-underline hover:prose-a:underline
            prose-code:bg-white/10 prose-code:text-accent prose-code:rounded prose-code:px-1
            prose-pre:bg-surface prose-pre:border prose-pre:border-border-neutral
            prose-blockquote:border-accent/40 prose-blockquote:text-text-secondary
            prose-strong:text-text-primary
            prose-li:text-text-secondary
            prose-hr:border-border-neutral
          ">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{article.content}</ReactMarkdown>
          </div>
        </>
      )}
    </div>
  )
}
```

Note: `prose` classes require `@tailwindcss/typography` plugin. If not installed, replace the `prose-*` wrapper with plain Tailwind classes. For simplicity, the prose classes are included; if the build fails due to the plugin not being installed, wrap content in a `<div className="text-text-secondary space-y-4">` instead and remove all `prose-*` classes.

**If @tailwindcss/typography is not installed**, update the article content wrapper to use plain styling:
```tsx
{/* Replace the prose div with: */}
<div className="[&_h1]:text-xl [&_h1]:font-bold [&_h1]:text-text-primary [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-text-primary [&_p]:text-text-secondary [&_p]:leading-relaxed [&_a]:text-accent [&_code]:bg-white/10 [&_code]:text-accent [&_code]:rounded [&_code]:px-1 [&_code]:text-sm [&_ul]:list-disc [&_ul]:pl-5 [&_li]:text-text-secondary [&_li]:mb-1 space-y-4">
```

- [ ] **Step 3: Type-check**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run type-check 2>&1 | head -30`
Expected: no errors

If there are TypeScript issues with react-markdown or remark-gfm imports, add `@types/react-markdown` or check if `@types` packages are needed.

- [ ] **Step 4: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/src/pages/DocsPage.tsx frontend/src/pages/DocsArticlePage.tsx
git commit -m "feat: implement Docs pages with article list and markdown rendering"
```

---

## Task 6: Support Page

**Files:**
- Create: `frontend/src/pages/SupportPage.tsx`

Logic:
- Display `support_telegram_url` setting — but this comes from the backend settings, which is an admin-only endpoint. For the public support page, the settings aren't exposed via a public API yet.
- **Workaround:** Use a static Telegram link placeholder that says "Telegram" or display a generic message. The contact form sends to the backend which reads the setting.
- Contact form: name (pre-filled from `user.display_name`), message textarea, Send button
- `POST /api/support/message {message: string}` — backend handles routing; returns 200 on success

- [ ] **Step 1: Create SupportPage.tsx**

```tsx
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
```

Note: The Telegram URL `https://t.me/skavellion_support` is a static placeholder. In a future iteration, expose the `support_telegram_url` setting via a public API endpoint (`GET /api/settings/public`). For now the hardcoded link works; admin can update by modifying this constant.

- [ ] **Step 2: Type-check**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run type-check 2>&1 | head -20`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/src/pages/SupportPage.tsx
git commit -m "feat: implement Support page with contact form"
```

---

## Task 7: Profile Page

**Files:**
- Create: `frontend/src/pages/ProfilePage.tsx`

Logic:
- Shows `UserProfileResponse`: display_name, id, created_at, providers list
- Linked providers: Telegram, Google, VK, Email icons
- Unlink button → `DELETE /api/users/me/providers/{provider}` → invalidate `['me']`
- Transaction history from `useTransactions()`
- Transaction type icons and labels

- [ ] **Step 1: Create ProfilePage.tsx**

```tsx
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { User, Trash2, Clock, Loader2, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useTransactions } from '@/hooks/useTransactions'
import { api, ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'

const PROVIDER_LABELS: Record<string, string> = {
  telegram: 'Telegram',
  google: 'Google',
  vk: 'VK',
  email: 'Email',
}

const PROVIDER_COLORS: Record<string, string> = {
  telegram: 'text-[#229ED9]',
  google: 'text-[#EA4335]',
  vk: 'text-[#0077FF]',
  email: 'text-text-muted',
}

const TX_TYPE_LABELS: Record<string, string> = {
  trial_activation: 'Пробный период',
  payment: 'Оплата',
  promo_bonus: 'Промокод',
  manual: 'Вручную',
}

const TX_STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle size={14} className="text-emerald-400 shrink-0" />,
  failed: <XCircle size={14} className="text-red-400 shrink-0" />,
  pending: <Clock size={14} className="text-yellow-400 shrink-0 animate-pulse" />,
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export default function ProfilePage() {
  const queryClient = useQueryClient()
  const { user, isLoading: authLoading } = useAuth()
  const { data: transactions = [], isLoading: txLoading } = useTransactions()

  const unlinkMutation = useMutation({
    mutationFn: (provider: string) =>
      api.delete(`/api/users/me/providers/${provider}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })

  if (authLoading) {
    return (
      <div className="p-6 flex justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  if (!user) return null

  const shortId = user.id.slice(0, 8).toUpperCase()

  return (
    <div className="p-4 md:p-6 max-w-xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Профиль</h1>

      {/* Account info */}
      <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
        <div className="flex items-center gap-4 mb-4">
          <div className="h-12 w-12 rounded-full bg-accent/20 flex items-center justify-center text-lg font-bold text-accent shrink-0">
            {user.display_name[0].toUpperCase()}
          </div>
          <div>
            <p className="font-semibold text-text-primary">{user.display_name}</p>
            <p className="text-xs text-text-muted">#{shortId}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-text-muted text-xs mb-0.5">Аккаунт создан</p>
            <p className="text-text-secondary">{formatDate(user.created_at)}</p>
          </div>
          <div>
            <p className="text-text-muted text-xs mb-0.5">Роль</p>
            <p className="text-text-secondary">{user.is_admin ? 'Администратор' : 'Пользователь'}</p>
          </div>
        </div>
      </div>

      {/* Linked providers */}
      <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
        <h2 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
          <User size={14} className="text-accent" /> Привязанные аккаунты
        </h2>
        {user.providers.length === 0 ? (
          <p className="text-xs text-text-muted">Нет привязанных аккаунтов</p>
        ) : (
          <div className="space-y-2">
            {user.providers.map((p) => (
              <div
                key={p.type}
                className="flex items-center justify-between rounded-input bg-white/5 px-3 py-2.5"
              >
                <div className="flex items-center gap-2.5">
                  <span className={cn('text-sm font-medium', PROVIDER_COLORS[p.type] ?? 'text-text-secondary')}>
                    {PROVIDER_LABELS[p.type] ?? p.type}
                  </span>
                  {p.username && (
                    <span className="text-xs text-text-muted">@{p.username}</span>
                  )}
                </div>
                {user.providers.length > 1 && (
                  <button
                    onClick={() => unlinkMutation.mutate(p.type)}
                    disabled={unlinkMutation.isPending}
                    className="text-text-muted hover:text-red-400 transition-colors disabled:opacity-50"
                    title="Отвязать"
                  >
                    {unlinkMutation.isPending ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Trash2 size={14} />
                    )}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {user.providers.length <= 1 && (
          <p className="mt-2 text-xs text-text-muted flex items-center gap-1.5">
            <AlertCircle size={12} />
            Нельзя отвязать единственный способ входа
          </p>
        )}
        {unlinkMutation.isError && (
          <p className="mt-2 text-xs text-red-400">
            {unlinkMutation.error instanceof ApiError ? unlinkMutation.error.detail : 'Ошибка'}
          </p>
        )}
      </div>

      {/* Transaction history */}
      <div className="rounded-card bg-surface border border-border-neutral p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-3">История операций</h2>
        {txLoading ? (
          <div className="flex justify-center py-4">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        ) : transactions.length === 0 ? (
          <p className="text-xs text-text-muted text-center py-4">Нет операций</p>
        ) : (
          <div className="space-y-2">
            {transactions.map((tx) => (
              <div
                key={tx.id}
                className="flex items-center gap-3 rounded-input bg-white/5 px-3 py-2.5"
              >
                {TX_STATUS_ICON[tx.status] ?? <Clock size={14} className="text-text-muted shrink-0" />}
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-text-primary truncate">
                    {TX_TYPE_LABELS[tx.type] ?? tx.type}
                    {tx.plan_name ? ` · ${tx.plan_name}` : ''}
                  </p>
                  <p className="text-[10px] text-text-muted">{formatDate(tx.created_at)}</p>
                </div>
                <div className="text-right shrink-0">
                  {tx.amount_rub != null && tx.amount_rub > 0 && (
                    <p className="text-xs text-text-primary">{tx.amount_rub}₽</p>
                  )}
                  {tx.days_added != null && (
                    <p className="text-[10px] text-emerald-400">+{tx.days_added} дн.</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Type-check**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run type-check 2>&1 | head -30`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/src/pages/ProfilePage.tsx
git commit -m "feat: implement Profile page with account info, providers, and transaction history"
```

---

## Task 8: Wire Up Routes + Final Build

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update App.tsx with all routes**

Replace `frontend/src/App.tsx` with:

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/Layout'
import ProtectedRoute from '@/components/ProtectedRoute'
import LoginPage from '@/pages/LoginPage'
import HomePage from '@/pages/HomePage'
import SubscriptionPage from '@/pages/SubscriptionPage'
import InstallPage from '@/pages/InstallPage'
import DocsPage from '@/pages/DocsPage'
import DocsArticlePage from '@/pages/DocsArticlePage'
import SupportPage from '@/pages/SupportPage'
import ProfilePage from '@/pages/ProfilePage'
import NotFoundPage from '@/pages/NotFoundPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/subscription" element={<SubscriptionPage />} />
            <Route path="/install" element={<InstallPage />} />
            <Route path="/docs" element={<DocsPage />} />
            <Route path="/docs/:slug" element={<DocsArticlePage />} />
            <Route path="/support" element={<SupportPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 2: Type-check**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run type-check 2>&1 | head -40`
Expected: 0 errors

- [ ] **Step 3: Build**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run build 2>&1 | tail -10`
Expected: build completes, `dist/` populated, no errors

- [ ] **Step 4: Fix any build errors**

Common issues:
- `@tailwindcss/typography` not installed → remove `prose-*` classes from `DocsArticlePage.tsx` and replace with inline Tailwind approach described in Task 5 Step 2
- Import path errors → verify all page imports match actual filenames
- Type errors in ReactMarkdown → ensure `react-markdown` types are bundled (no separate `@types` needed for v9)

- [ ] **Step 5: Final commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/src/App.tsx
git commit -m "feat: wire up all user page routes in App.tsx"
```

---

## Final Verification

- [ ] `npm run type-check` → 0 errors
- [ ] `npm run build` → build succeeds
- [ ] All 6 pages reachable via routes in `App.tsx`
- [ ] No unused imports (TypeScript strict mode will catch these)

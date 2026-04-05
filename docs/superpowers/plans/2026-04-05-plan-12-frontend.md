# Plan 12: Email Verification & Admin Enhancements — Frontend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add email verification UI, admin user detail actions, and new admin settings sections to the frontend.

**Architecture:** TypeScript types updated first. New `VerifyEmailPage` (standalone, no auth). New `EmailVerificationBanner` component shown on home/subscription. Admin user detail page redesigned with info grid + action buttons. Admin settings page gains new grouped sections.

**Tech Stack:** React 18, TypeScript 5, TanStack Query v5, React Router v6, Tailwind CSS 3, lucide-react

**Prerequisite:** Plan 11 (backend) must be deployed — these changes depend on new API fields.

**Type check:** `cd frontend && npm run type-check`
**Build:** `cd frontend && npm run build`

---

## File Map

**New files:**
- `frontend/src/pages/VerifyEmailPage.tsx`
- `frontend/src/components/EmailVerificationBanner.tsx`

**Modified files:**
- `frontend/src/types/api.ts` — add new fields to existing interfaces + new `OAuthConfigResponse` type
- `frontend/src/App.tsx` — add `/verify-email` route
- `frontend/src/pages/HomePage.tsx` — add banner
- `frontend/src/pages/SubscriptionPage.tsx` — add banner + trial button guard
- `frontend/src/pages/admin/AdminUserDetailPage.tsx` — full redesign with actions
- `frontend/src/pages/admin/AdminSettingsPage.tsx` — new grouped sections

---

## Task 1: Update TypeScript types

**Files:**
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add new fields to existing interfaces and add missing types**

**IMPORTANT shape note:** The user-facing `ProviderInfo` interface (used by `UserProfile.providers`) is served by `GET /api/users/me` which returns `{type, username, identifier}`. This shape must NOT change — it is used throughout `LoginPage`, `ProfilePage`, etc. Only `AdminProviderInfo` (served by `GET /api/admin/users/:id`) needs `email_verified` added.

In `frontend/src/types/api.ts`:

**Update `UserProfile`** (add `email_verified`):
```typescript
export interface UserProfile {
  id: string
  display_name: string
  is_admin: boolean
  created_at: string
  providers: ProviderInfo[]
  email_verified: boolean | null   // null = no email provider
}
```

**Update `AdminProviderInfo`** (add `email_verified`):
```typescript
export interface AdminProviderInfo {
  provider: string
  provider_user_id: string
  provider_username: string | null
  email_verified: boolean | null   // null for OAuth providers
  created_at: string
}
```

**Update `UserAdminListItem`** (add `is_banned`, `email`, `email_verified`, and missing fields):
```typescript
export interface UserAdminListItem {
  id: string
  display_name: string
  avatar_url: string | null
  is_admin: boolean
  is_banned: boolean
  email: string | null
  email_verified: boolean | null
  providers: string[]
  subscription_status: string | null
  subscription_type: string | null
  subscription_expires_at: string | null
  remnawave_uuid: string | null
  subscription_conflict: boolean
  has_made_payment: boolean
  created_at: string
  last_seen_at: string
}
```

**Update `UserAdminDetail`** (add `is_banned`, `email`, `email_verified`):
```typescript
export interface UserAdminDetail {
  id: string
  display_name: string
  avatar_url: string | null
  is_admin: boolean
  is_banned: boolean
  email: string | null
  email_verified: boolean | null
  has_made_payment: boolean
  subscription_conflict: boolean
  remnawave_uuid: string | null
  created_at: string
  last_seen_at: string
  providers: AdminProviderInfo[]
  subscription: AdminSubscriptionInfo | null
  recent_transactions: AdminTransactionItem[]
}
```

**Add `OAuthConfigResponse`** (new type, add below existing types in the Plan 11 section):
```typescript
export interface OAuthConfigResponse {
  google: boolean
  google_client_id: string | null
  vk: boolean
  vk_client_id: string | null
  telegram: boolean
  telegram_bot_username: string | null
  email_enabled: boolean
  support_telegram_url: string | null
  email_verification_required: boolean
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npm run type-check
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat: update TypeScript types for Plan 12 (email_verified, is_banned, OAuthConfigResponse)"
```

---

## Task 2: `/verify-email` page

**Files:**
- Create: `frontend/src/pages/VerifyEmailPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/pages/VerifyEmailPage.tsx`**

```tsx
import { useSearchParams, Link } from 'react-router-dom'
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react'

export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const verified = params.get('verified')
  const error = params.get('error')

  if (verified === '1') {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-4">
        <div className="max-w-sm w-full text-center space-y-6">
          <CheckCircle className="mx-auto text-green-400" size={48} />
          <h1 className="text-xl font-semibold text-text-primary">Email подтверждён</h1>
          <p className="text-sm text-text-secondary">
            Ваш адрес электронной почты успешно подтверждён. Теперь вы можете активировать пробный период.
          </p>
          <Link
            to="/subscription"
            className="inline-block w-full py-2.5 px-4 rounded-input bg-accent text-background text-sm font-semibold text-center hover:bg-accent/90 transition-colors"
          >
            Перейти к подписке
          </Link>
        </div>
      </div>
    )
  }

  if (error === 'expired') {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-4">
        <div className="max-w-sm w-full text-center space-y-6">
          <XCircle className="mx-auto text-red-400" size={48} />
          <h1 className="text-xl font-semibold text-text-primary">Ссылка устарела</h1>
          <p className="text-sm text-text-secondary">
            Ссылка для подтверждения недействительна или истекла. Запросите новую ссылку на главной странице.
          </p>
          <Link
            to="/"
            className="inline-block w-full py-2.5 px-4 rounded-input bg-surface border border-border-neutral text-text-primary text-sm font-semibold text-center hover:border-accent transition-colors"
          >
            На главную
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="max-w-sm w-full text-center space-y-6">
        <AlertCircle className="mx-auto text-text-muted" size={48} />
        <h1 className="text-xl font-semibold text-text-primary">Неверная ссылка</h1>
        <p className="text-sm text-text-secondary">
          Эта ссылка недействительна.
        </p>
        <Link
          to="/"
          className="inline-block w-full py-2.5 px-4 rounded-input bg-surface border border-border-neutral text-text-primary text-sm font-semibold text-center hover:border-accent transition-colors"
        >
          На главную
        </Link>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add route to `frontend/src/App.tsx`**

Add import:
```typescript
import VerifyEmailPage from '@/pages/VerifyEmailPage'
```

Add route before the admin routes block (standalone — no Layout, no auth):
```tsx
<Route path="/verify-email" element={<VerifyEmailPage />} />
```

- [ ] **Step 3: Type-check and build**

```bash
cd frontend && npm run type-check && npm run build
```
Expected: 0 errors, build success

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/VerifyEmailPage.tsx frontend/src/App.tsx
git commit -m "feat: add /verify-email standalone page"
```

---

## Task 3: `EmailVerificationBanner` component

**Files:**
- Create: `frontend/src/components/EmailVerificationBanner.tsx`

- [ ] **Step 1: Create `frontend/src/components/EmailVerificationBanner.tsx`**

```tsx
import { useState, useRef } from 'react'
import { AlertTriangle, Send, CheckCircle } from 'lucide-react'
import { api, ApiError } from '@/lib/api'

interface Props {
  // Pass through so the banner doesn't need to re-fetch these values
  userEmail: string   // display only — the email address to confirm
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
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EmailVerificationBanner.tsx
git commit -m "feat: add EmailVerificationBanner component"
```

---

## Task 4: Add banner to HomePage and SubscriptionPage + trial guard

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/pages/SubscriptionPage.tsx`

- [ ] **Step 1: Add banner to `HomePage.tsx`**

Read `frontend/src/pages/HomePage.tsx` to understand the current structure.

Add at the top of the component:
```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { OAuthConfigResponse } from '@/types/api'
import EmailVerificationBanner from '@/components/EmailVerificationBanner'
import { useAuth } from '@/hooks/useAuth'
```

Inside the component, add:
```tsx
const { user } = useAuth()
const { data: oauthConfig } = useQuery<OAuthConfigResponse>({
  queryKey: ['oauthConfig'],
  queryFn: () => api.get<OAuthConfigResponse>('/api/auth/oauth-config'),
  staleTime: 300_000,
})

const showVerifyBanner =
  user?.email_verified === false &&
  oauthConfig?.email_verification_required === true
```

Find the email address of the user:
```tsx
const emailProvider = user?.providers.find(p => p.type === 'email')
```

At the top of the JSX return (inside the page container, above existing content), add:
```tsx
{showVerifyBanner && emailProvider?.identifier && (
  <EmailVerificationBanner userEmail={emailProvider.identifier} />
)}
```

- [ ] **Step 2: Add banner and trial guard to `SubscriptionPage.tsx`**

Read `frontend/src/pages/SubscriptionPage.tsx` to understand the current structure.

Same oauth config query and `showVerifyBanner` logic as HomePage.

Wrap the "Активировать пробный период" button with a `title` attribute and `disabled` state:
```tsx
<button
  onClick={handleActivateTrial}
  disabled={trialMutation.isPending || showVerifyBanner}
  title={showVerifyBanner ? 'Сначала подтвердите email' : undefined}
  className={`... ${showVerifyBanner ? 'opacity-50 cursor-not-allowed' : ''}`}
>
  Активировать пробный период
</button>
```

Place the banner above the trial section:
```tsx
{showVerifyBanner && emailProvider?.identifier && (
  <EmailVerificationBanner userEmail={emailProvider.identifier} />
)}
```

- [ ] **Step 3: Type-check and build**

```bash
cd frontend && npm run type-check && npm run build
```
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/HomePage.tsx frontend/src/pages/SubscriptionPage.tsx
git commit -m "feat: show email verification banner on Home and Subscription pages"
```

---

## Task 5: Admin user detail page redesign

**Files:**
- Modify: `frontend/src/pages/admin/AdminUserDetailPage.tsx`

- [ ] **Step 1: Rewrite `AdminUserDetailPage.tsx`**

Full replacement. The page must preserve existing functionality (sync, resolve-conflict) and add new actions (ban, toggle-admin, reset-subscription).

```tsx
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, RefreshCw, Shield, ShieldOff, UserCheck, UserX,
  RotateCcw, CheckCircle, XCircle, AlertTriangle,
} from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import type { UserAdminDetail, ConflictResolveRequest } from '@/types/api'

// ─── Confirmation dialog ──────────────────────────────────────────────────────

interface ConfirmDialogProps {
  message: string
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDialog({ message, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
      <div className="bg-surface border border-border-neutral rounded-card p-6 max-w-sm w-full space-y-4">
        <p className="text-sm text-text-primary">{message}</p>
        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            className="flex-1 py-2 rounded-input bg-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/30 transition-colors"
          >
            Подтвердить
          </button>
          <button
            onClick={onCancel}
            className="flex-1 py-2 rounded-input bg-surface border border-border-neutral text-text-secondary text-sm hover:border-accent transition-colors"
          >
            Отмена
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Info row ────────────────────────────────────────────────────────────────

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4 py-2 border-b border-border-neutral/50 last:border-0">
      <span className="text-xs text-text-muted sm:w-36 shrink-0">{label}</span>
      <span className="text-sm text-text-primary break-all">{value ?? '—'}</span>
    </div>
  )
}

// ─── Action button ───────────────────────────────────────────────────────────

function ActionBtn({
  onClick, icon, label, variant = 'default', disabled,
}: {
  onClick: () => void
  icon: React.ReactNode
  label: string
  variant?: 'default' | 'danger'
  disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-2 px-3 py-2 rounded-input text-xs font-medium transition-colors disabled:opacity-50 ${
        variant === 'danger'
          ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20'
          : 'bg-surface border border-border-neutral text-text-secondary hover:border-accent hover:text-accent'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user: currentAdmin } = useAuth()

  const [resolveUuid, setResolveUuid] = useState('')
  const [confirm, setConfirm] = useState<{ message: string; action: () => void } | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const flash = (text: string) => {
    setMsg(text)
    setTimeout(() => setMsg(null), 3000)
  }

  const { data: user, isLoading, error } = useQuery<UserAdminDetail>({
    queryKey: ['admin-user', id],
    queryFn: () => api.get<UserAdminDetail>(`/api/admin/users/${id}`),
    enabled: !!id,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin-user', id] })

  const banMutation = useMutation({
    mutationFn: () => api.patch(`/api/admin/users/${id}/ban`, {}),
    onSuccess: (updated: UserAdminDetail) => {
      queryClient.setQueryData(['admin-user', id], updated)
      flash(updated.is_banned ? 'Пользователь заблокирован' : 'Пользователь разблокирован')
    },
  })

  const adminMutation = useMutation({
    mutationFn: () => api.patch(`/api/admin/users/${id}/admin`, {}),
    onSuccess: (updated: UserAdminDetail) => {
      queryClient.setQueryData(['admin-user', id], updated)
      flash(updated.is_admin ? 'Права администратора выданы' : 'Права администратора отозваны')
    },
  })

  const resetSubMutation = useMutation({
    mutationFn: () => api.post(`/api/admin/users/${id}/reset-subscription`, {}),
    onSuccess: () => {
      invalidate()
      flash('Подписка сброшена')
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => api.post(`/api/admin/users/${id}/sync`, {}),
    onSuccess: () => { invalidate(); flash('Синхронизация выполнена') },
  })

  const resolveMutation = useMutation({
    mutationFn: (data: ConflictResolveRequest) =>
      api.post(`/api/admin/users/${id}/resolve-conflict`, data),
    onSuccess: () => {
      invalidate()
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setResolveUuid('')
      flash('Конфликт разрешён')
    },
  })

  const askConfirm = (message: string, action: () => void) =>
    setConfirm({ message, action })

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  if (error || !user) {
    return (
      <div className="p-6">
        <p className="text-xs text-red-400">
          {error instanceof ApiError ? error.detail : 'Пользователь не найден'}
        </p>
      </div>
    )
  }

  const isSelf = currentAdmin?.id === user.id
  const sub = user.subscription

  return (
    <div className="max-w-2xl mx-auto space-y-6 p-4 sm:p-6">
      {confirm && (
        <ConfirmDialog
          message={confirm.message}
          onConfirm={() => { confirm.action(); setConfirm(null) }}
          onCancel={() => setConfirm(null)}
        />
      )}

      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/admin/users')}
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-semibold text-text-primary truncate">{user.display_name}</h1>
        {user.is_banned && (
          <span className="px-2 py-0.5 rounded text-xs bg-red-500/15 text-red-400">Заблокирован</span>
        )}
        {user.is_admin && (
          <span className="px-2 py-0.5 rounded text-xs bg-accent/15 text-accent">Админ</span>
        )}
      </div>

      {msg && (
        <div className="flex items-center gap-2 text-xs text-green-400 bg-green-500/10 rounded-input px-3 py-2">
          <CheckCircle size={13} />
          {msg}
        </div>
      )}

      {/* Info section */}
      <div className="rounded-card bg-surface border border-border-neutral p-4 sm:p-5 space-y-0.5">
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">
          Информация
        </h2>
        <InfoRow label="ID" value={<span className="font-mono text-xs">{user.id}</span>} />
        <InfoRow
          label="Email"
          value={
            user.email ? (
              <span className="flex items-center gap-2">
                {user.email}
                {user.email_verified === true && (
                  <CheckCircle size={13} className="text-green-400 shrink-0" />
                )}
                {user.email_verified === false && (
                  <XCircle size={13} className="text-yellow-400 shrink-0" />
                )}
              </span>
            ) : null
          }
        />
        <InfoRow
          label="Провайдеры"
          value={
            <div className="space-y-1">
              {user.providers.map((p) => (
                <div key={p.provider} className="flex items-center gap-2 text-xs">
                  <span className="font-medium text-text-primary capitalize">{p.provider}</span>
                  {p.provider_username && (
                    <span className="text-text-muted">@{p.provider_username}</span>
                  )}
                  {p.provider_user_id && (
                    <span className="font-mono text-text-muted">{p.provider_user_id}</span>
                  )}
                </div>
              ))}
            </div>
          }
        />
        <InfoRow label="Создан" value={new Date(user.created_at).toLocaleString('ru-RU')} />
        <InfoRow label="Последний вход" value={new Date(user.last_seen_at).toLocaleString('ru-RU')} />
        <InfoRow
          label="Подписка"
          value={
            sub ? (
              <span>
                {sub.type} · {sub.status} · до {new Date(sub.expires_at).toLocaleDateString('ru-RU')}
                {sub.traffic_limit_gb != null && ` · ${sub.traffic_limit_gb} ГБ`}
              </span>
            ) : null
          }
        />
        <InfoRow
          label="Remnawave UUID"
          value={
            user.remnawave_uuid ? (
              <span className="font-mono text-xs">{user.remnawave_uuid}</span>
            ) : null
          }
        />
      </div>

      {/* Actions */}
      <div className="rounded-card bg-surface border border-border-neutral p-4 sm:p-5 space-y-4">
        <h2 className="text-xs font-medium text-text-muted uppercase tracking-wider">
          Действия
        </h2>

        <div className="flex flex-wrap gap-2">
          {/* Ban */}
          <ActionBtn
            onClick={() =>
              askConfirm(
                user.is_banned
                  ? `Разблокировать пользователя ${user.display_name}?`
                  : `Заблокировать пользователя ${user.display_name}?`,
                () => banMutation.mutate(),
              )
            }
            icon={user.is_banned ? <Shield size={14} /> : <ShieldOff size={14} />}
            label={user.is_banned ? 'Разблокировать' : 'Заблокировать'}
            variant={user.is_banned ? 'default' : 'danger'}
            disabled={isSelf || banMutation.isPending}
          />

          {/* Admin toggle */}
          <ActionBtn
            onClick={() =>
              askConfirm(
                user.is_admin
                  ? `Забрать права администратора у ${user.display_name}?`
                  : `Выдать права администратора ${user.display_name}?`,
                () => adminMutation.mutate(),
              )
            }
            icon={user.is_admin ? <UserX size={14} /> : <UserCheck size={14} />}
            label={user.is_admin ? 'Забрать права' : 'Сделать админом'}
            disabled={isSelf || adminMutation.isPending}
          />

          {/* Reset subscription */}
          <ActionBtn
            onClick={() =>
              askConfirm(
                `Сбросить подписку пользователя ${user.display_name}? Локальный сброс — Remnawave не затронут.`,
                () => resetSubMutation.mutate(),
              )
            }
            icon={<RotateCcw size={14} />}
            label="Сбросить подписку"
            variant="danger"
            disabled={!sub || resetSubMutation.isPending}
          />

          {/* Sync */}
          <ActionBtn
            onClick={() =>
              askConfirm(
                `Синхронизировать ${user.display_name} с Remnawave?`,
                () => syncMutation.mutate(),
              )
            }
            icon={<RefreshCw size={14} />}
            label="Синхронизировать"
            disabled={!user.remnawave_uuid || syncMutation.isPending}
          />
        </div>

        {/* Resolve conflict */}
        {user.subscription_conflict && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs text-yellow-400">
              <AlertTriangle size={13} />
              Конфликт UUID — введите правильный Remnawave UUID:
            </div>
            <div className="flex gap-2">
              <input
                value={resolveUuid}
                onChange={(e) => setResolveUuid(e.target.value)}
                placeholder="UUID из Remnawave"
                className="flex-1 rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent font-mono"
              />
              <button
                onClick={() => resolveMutation.mutate({ remnawave_uuid: resolveUuid })}
                disabled={!resolveUuid.trim() || resolveMutation.isPending}
                className="px-3 py-1.5 rounded-input bg-accent/10 text-accent text-xs font-medium hover:bg-accent/20 transition-colors disabled:opacity-50"
              >
                Применить
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Recent transactions */}
      {user.recent_transactions.length > 0 && (
        <div className="rounded-card bg-surface border border-border-neutral p-4 sm:p-5 space-y-3">
          <h2 className="text-xs font-medium text-text-muted uppercase tracking-wider">
            Последние транзакции
          </h2>
          <div className="space-y-2">
            {user.recent_transactions.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between text-xs">
                <span className="text-text-secondary">{tx.type}</span>
                <span className="text-text-muted">{new Date(tx.created_at).toLocaleDateString('ru-RU')}</span>
                <span className={tx.status === 'completed' ? 'text-green-400' : 'text-text-muted'}>
                  {tx.status}
                </span>
                {tx.days_added != null && (
                  <span className="text-accent">+{tx.days_added}д</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Type-check and build**

```bash
cd frontend && npm run type-check && npm run build
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminUserDetailPage.tsx
git commit -m "feat: redesign admin user detail page with ban/admin/reset actions"
```

---

## Task 6: Admin settings — new sections

**Files:**
- Modify: `frontend/src/pages/admin/AdminSettingsPage.tsx`

- [ ] **Step 1: Read the full current `AdminSettingsPage.tsx`** to understand the complete structure before editing.

- [ ] **Step 2: Add new key sets and specialized components**

In `AdminSettingsPage.tsx`, after the existing `OAUTH_KEYS` and `INSTALL_KEY_PREFIX` constants, add:

```typescript
const REMNAWAVE_KEYS = new Set([
  'remnawave_url', 'remnawave_token',
  'remnawave_trial_squad_uuids', 'remnawave_paid_squad_uuids',
])

const TRIAL_KEYS = new Set([
  'remnawave_trial_days', 'remnawave_trial_traffic_limit_bytes',
])

const EMAIL_SERVICE_KEYS = new Set([
  'resend_api_key', 'email_from_address', 'email_from_name',
])

const REGISTRATION_KEYS = new Set([
  'registration_enabled', 'email_verification_enabled', 'allowed_email_domains',
])
```

- [ ] **Step 3: Add `ToggleSettingRow` component** (for boolean settings stored as `"true"`/`"false"`):

```tsx
function ToggleSettingRow({ setting, label, hint }: { setting: SettingAdminItem; label: string; hint?: string }) {
  const queryClient = useQueryClient()
  const [isOn, setIsOn] = useState(setting.value === 'true')
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v }),
    onSuccess: (_, v) => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setIsOn(v === 'true')
      setSaveError(null)
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  const toggle = () => {
    const newVal = isOn ? 'false' : 'true'
    setIsOn(!isOn)
    mutation.mutate(newVal)
  }

  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-text-primary">{label}</p>
          {hint && <p className="text-xs text-text-muted mt-0.5">{hint}</p>}
        </div>
        <button
          onClick={toggle}
          disabled={mutation.isPending}
          className={`relative w-10 h-5 rounded-full transition-colors ${isOn ? 'bg-accent' : 'bg-surface border border-border-neutral'}`}
        >
          <span
            className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${isOn ? 'translate-x-5' : ''}`}
          />
        </button>
      </div>
      {saveError && <p className="mt-1 text-xs text-red-400">{saveError}</p>}
    </div>
  )
}
```

- [ ] **Step 4: Add `TextareaSettingRow` component** (for `allowed_email_domains`):

```tsx
function TextareaSettingRow({ setting, label, hint }: { setting: SettingAdminItem; label: string; hint?: string }) {
  const queryClient = useQueryClient()
  // Display as one domain per line, store as comma-separated
  const [value, setValue] = useState(
    (setting.value ?? '').split(',').map(d => d.trim()).filter(Boolean).join('\n')
  )
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setSaved(true)
      setSaveError(null)
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  const handleSave = () => {
    const normalized = value
      .split('\n')
      .map(d => d.trim().toLowerCase())
      .filter(Boolean)
      .join(',')
    mutation.mutate(normalized)
  }

  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3 space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-text-primary">{label}</p>
          {hint && <p className="text-xs text-text-muted mt-0.5">{hint}</p>}
        </div>
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-input text-xs font-medium transition-colors ${
            saved ? 'bg-green-500/20 text-green-400' : 'bg-accent/10 text-accent hover:bg-accent/20'
          } disabled:opacity-50`}
        >
          <Save size={13} />
          {saved ? 'Сохранено' : 'Сохранить'}
        </button>
      </div>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={6}
        placeholder="gmail.com&#10;mail.ru&#10;yandex.ru"
        className="w-full rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent font-mono resize-none"
      />
      {saveError && <p className="text-xs text-red-400">{saveError}</p>}
    </div>
  )
}
```

- [ ] **Step 5: Add `NumberBytesSettingRow` component** (for traffic limit in GB/bytes):

```tsx
function NumberBytesSettingRow({ setting, label, hint }: { setting: SettingAdminItem; label: string; hint?: string }) {
  const queryClient = useQueryClient()
  const GB = 1024 ** 3
  const [value, setValue] = useState(
    setting.value ? String(Math.round(parseInt(setting.value, 10) / GB)) : ''
  )
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setSaved(true)
      setSaveError(null)
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  const handleSave = () => {
    const gb = parseInt(value, 10)
    if (isNaN(gb) || gb <= 0) { setSaveError('Введите корректное число ГБ'); return }
    mutation.mutate(String(gb * GB))
  }

  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="text-sm text-text-primary">{label}</p>
          {hint && <p className="text-xs text-text-muted mt-0.5">{hint}</p>}
        </div>
      </div>
      <div className="flex gap-2 items-center">
        <input
          type="number"
          min={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-28 rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
        />
        <span className="text-sm text-text-secondary">ГБ</span>
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className={`ml-auto flex items-center gap-1 px-3 py-1.5 rounded-input text-xs font-medium transition-colors ${
            saved ? 'bg-green-500/20 text-green-400' : 'bg-accent/10 text-accent hover:bg-accent/20'
          } disabled:opacity-50`}
        >
          <Save size={13} />
          {saved ? 'Сохранено' : 'Сохранить'}
        </button>
      </div>
      {saveError && <p className="mt-1 text-xs text-red-400">{saveError}</p>}
    </div>
  )
}
```

- [ ] **Step 6: Replace the settings render section with new grouped layout**

After reading the full file in Step 1, locate where the component renders settings groups (there will be a JSX block using `oauthSettings`, `installSettings`, etc.). Replace that section with the following complete render structure:

```tsx
{/* Read existing file structure first — locate the settings groups JSX and replace with this */}

{/* Filter settings into groups */}
{(() => {
  const remnawave = settings.filter(s => REMNAWAVE_KEYS.has(s.key))
  const trial = settings.filter(s => TRIAL_KEYS.has(s.key))
  const emailService = settings.filter(s => EMAIL_SERVICE_KEYS.has(s.key))
  const registration = settings.filter(s => REGISTRATION_KEYS.has(s.key))
  const oauthSettings = settings.filter(s => OAUTH_KEYS.has(s.key))
  const installSettings = settings.filter(s => s.key.startsWith(INSTALL_KEY_PREFIX))
  const otherSettings = settings.filter(
    s =>
      !REMNAWAVE_KEYS.has(s.key) &&
      !TRIAL_KEYS.has(s.key) &&
      !EMAIL_SERVICE_KEYS.has(s.key) &&
      !REGISTRATION_KEYS.has(s.key) &&
      !OAUTH_KEYS.has(s.key) &&
      !s.key.startsWith(INSTALL_KEY_PREFIX),
  )

  return (
    <div className="space-y-8">
      {/* Remnawave */}
      {remnawave.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-text-secondary mb-3">Remnawave</h2>
          <div className="space-y-2">
            {remnawave.map(s => (
              <SettingRow
                key={s.key}
                setting={s}
                labelOverride={SETTING_LABELS[s.key]}
                hint={
                  s.key === 'remnawave_trial_squad_uuids'
                    ? 'UUID через запятую. Если пусто — используется устаревший ключ remnawave_squad_uuids'
                    : undefined
                }
              />
            ))}
          </div>
        </section>
      )}

      {/* Пробный период */}
      {trial.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-text-secondary mb-3">Пробный период</h2>
          <div className="space-y-2">
            {trial.map(s =>
              s.key === 'remnawave_trial_traffic_limit_bytes' ? (
                <NumberBytesSettingRow
                  key={s.key}
                  setting={s}
                  label={SETTING_LABELS[s.key] ?? s.key}
                />
              ) : (
                <SettingRow key={s.key} setting={s} labelOverride={SETTING_LABELS[s.key]} />
              ),
            )}
          </div>
        </section>
      )}

      {/* Email-сервис */}
      {emailService.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-text-secondary mb-3">Email-сервис (Resend)</h2>
          <div className="space-y-2">
            {emailService.map(s => (
              <SettingRow key={s.key} setting={s} labelOverride={SETTING_LABELS[s.key]} />
            ))}
          </div>
        </section>
      )}

      {/* Регистрация */}
      {registration.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-text-secondary mb-3">Регистрация</h2>
          <div className="space-y-2">
            {registration.map(s => {
              if (s.key === 'allowed_email_domains') {
                return (
                  <TextareaSettingRow
                    key={s.key}
                    setting={s}
                    label={SETTING_LABELS[s.key] ?? s.key}
                    hint="Один домен на строку. Если пусто — разрешены все домены."
                  />
                )
              }
              if (s.key === 'registration_enabled' || s.key === 'email_verification_enabled') {
                return (
                  <ToggleSettingRow
                    key={s.key}
                    setting={s}
                    label={SETTING_LABELS[s.key] ?? s.key}
                  />
                )
              }
              return <SettingRow key={s.key} setting={s} labelOverride={SETTING_LABELS[s.key]} />
            })}
          </div>
        </section>
      )}

      {/* OAuth — existing section, keep as-is */}
      {oauthSettings.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-text-secondary mb-3">OAuth</h2>
          <div className="space-y-2">
            {oauthSettings.map(s => (
              <SettingRow key={s.key} setting={s} />
            ))}
          </div>
        </section>
      )}

      {/* Приложения — existing section, keep as-is */}
      {installSettings.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-text-secondary mb-3">Приложения</h2>
          <div className="space-y-2">
            {installSettings.map(s => (
              <SettingRow key={s.key} setting={s} />
            ))}
          </div>
        </section>
      )}

      {/* Прочее */}
      {otherSettings.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-text-secondary mb-3">Прочее</h2>
          <div className="space-y-2">
            {otherSettings.map(s => (
              <SettingRow key={s.key} setting={s} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
})()}
```

Note: `SettingRow` needs an optional `labelOverride?: string` and `hint?: string` prop. Add these to its `Props` interface and render them above the input if present. Example addition:
```tsx
function SettingRow({ setting, labelOverride, hint }: { setting: SettingAdminItem; labelOverride?: string; hint?: string }) {
  // ... existing state
  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3">
      {(labelOverride || hint) && (
        <div className="mb-2">
          {labelOverride && <p className="text-sm text-text-primary">{labelOverride}</p>}
          {hint && <p className="text-xs text-text-muted mt-0.5">{hint}</p>}
        </div>
      )}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-text-muted">{setting.key}</span>
        {/* ... sensitive badge */}
      </div>
      {/* ... rest of existing JSX */}
    </div>
  )
}
```

- [ ] **Step 7: Read the file labels mapping**

Add a `SETTING_LABELS` map for human-readable names:
```typescript
const SETTING_LABELS: Record<string, string> = {
  remnawave_url: 'URL сервера Remnawave',
  remnawave_token: 'API токен Remnawave',
  remnawave_trial_squad_uuids: 'Squad UUID для триала',
  remnawave_paid_squad_uuids: 'Squad UUID для платной подписки',
  remnawave_trial_days: 'Длительность триала (дней)',
  remnawave_trial_traffic_limit_bytes: 'Лимит трафика триала',
  resend_api_key: 'API ключ Resend',
  email_from_address: 'Адрес отправителя',
  email_from_name: 'Имя отправителя',
  registration_enabled: 'Регистрация открыта',
  email_verification_enabled: 'Подтверждение email обязательно',
  allowed_email_domains: 'Разрешённые домены',
}
```

Pass the label to each specialized row component.

- [ ] **Step 8: Type-check and build**

```bash
cd frontend && npm run type-check && npm run build
```
Expected: 0 errors, build ≤ 600 KB JS

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/admin/AdminSettingsPage.tsx
git commit -m "feat: add Remnawave, email-service, registration sections to admin settings"
```

---

## Task 7: Final verification

- [ ] **Step 1: Full type-check and build**

```bash
cd frontend && npm run type-check && npm run build
```
Expected: 0 TypeScript errors, clean build

- [ ] **Step 2: Final commit**

```bash
git add frontend/src/types/api.ts \
        frontend/src/App.tsx \
        frontend/src/pages/VerifyEmailPage.tsx \
        frontend/src/components/EmailVerificationBanner.tsx \
        frontend/src/pages/HomePage.tsx \
        frontend/src/pages/SubscriptionPage.tsx \
        frontend/src/pages/admin/AdminUserDetailPage.tsx \
        frontend/src/pages/admin/AdminSettingsPage.tsx
git commit -m "feat: Plan 12 complete — email verification UI, admin user actions, admin settings"
```

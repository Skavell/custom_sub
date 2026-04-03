# Plan 10: Admin Panel Frontend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete admin panel frontend (`/admin/*`) — 9 pages, AdminRoute guard, AdminLayout sidebar, and all required TypeScript types — consuming the already-complete backend admin API.

**Architecture:** Admin pages live in `src/pages/admin/`. `AdminRoute` wraps all admin routes (checks `is_admin`, redirects to `/` if false). `AdminLayout` provides a separate sidebar with admin nav items. All data fetching is via inline `useQuery`/`useMutation` calls (no separate hook files — YAGNI, nothing is reused). Types appended to existing `src/types/api.ts`.

**Tech Stack:** React 18, TanStack Query v5, React Router v6, Tailwind CSS 3, lucide-react, react-markdown + remark-gfm (articles), existing `api` client from `src/lib/api.ts`

---

## Backend API Reference (all require admin cookie + `is_admin=true`)

| Method | Path | Used by |
|--------|------|---------|
| GET | `/api/admin/users?page=&per_page=&search=` | AdminUsersPage |
| GET | `/api/admin/users/{id}` | AdminUserDetailPage |
| POST | `/api/admin/users/{id}/sync` | AdminUserDetailPage |
| POST | `/api/admin/users/{id}/resolve-conflict` | AdminUserDetailPage |
| POST | `/api/admin/sync/all` | AdminSyncPage |
| GET | `/api/admin/sync/status/{task_id}` | AdminSyncPage |
| GET | `/api/admin/plans` | AdminPlansPage |
| PATCH | `/api/admin/plans/{id}` | AdminPlansPage |
| GET | `/api/admin/promo-codes` | AdminPromoCodesPage |
| POST | `/api/admin/promo-codes` | AdminPromoCodesPage |
| PATCH | `/api/admin/promo-codes/{id}/toggle` | AdminPromoCodesPage |
| DELETE | `/api/admin/promo-codes/{id}` | AdminPromoCodesPage |
| GET | `/api/admin/articles` | AdminArticlesPage |
| POST | `/api/admin/articles/{id}/publish` | AdminArticlesPage |
| POST | `/api/admin/articles/{id}/unpublish` | AdminArticlesPage |
| DELETE | `/api/admin/articles/{id}` | AdminArticlesPage |
| GET | `/api/admin/articles/{id}` | AdminArticleEditPage |
| POST | `/api/admin/articles` | AdminArticleEditPage |
| PATCH | `/api/admin/articles/{id}` | AdminArticleEditPage |
| GET | `/api/admin/settings` | AdminSettingsPage |
| PUT | `/api/admin/settings/{key}` | AdminSettingsPage |
| GET | `/api/admin/support-messages?skip=&limit=` | AdminSupportMessagesPage |

## Files Created/Modified

```
frontend/src/
├── types/api.ts                        MODIFY  — append admin types
├── App.tsx                             MODIFY  — add /admin/* routes
├── components/
│   ├── AdminRoute.tsx                  CREATE  — guard: auth + is_admin
│   └── AdminLayout.tsx                 CREATE  — sidebar for admin nav
└── pages/admin/
    ├── AdminUsersPage.tsx              CREATE  — user list, search, pagination
    ├── AdminUserDetailPage.tsx         CREATE  — user detail, sync, resolve conflict
    ├── AdminSyncPage.tsx               CREATE  — sync all + polling progress
    ├── AdminPlansPage.tsx              CREATE  — inline plan editing
    ├── AdminPromoCodesPage.tsx         CREATE  — promo code list + create form
    ├── AdminArticlesPage.tsx           CREATE  — article list, publish, delete
    ├── AdminArticleEditPage.tsx        CREATE  — create/edit with markdown preview
    ├── AdminSettingsPage.tsx           CREATE  — grouped settings form
    └── AdminSupportMessagesPage.tsx    CREATE  — paginated support log
```

---

## Task 1: Admin Types

**Files:**
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Append admin types to `src/types/api.ts`**

Add at the end of the file (after `CreatePaymentRequest`):

```typescript
// ─── Admin types (Plan 10) ───────────────────────────────────────────────────

// Admin-specific provider info (different from user-facing ProviderInfo)
export interface AdminProviderInfo {
  provider: string
  provider_user_id: string
  provider_username: string | null
  created_at: string
}

export interface UserAdminListItem {
  id: string
  display_name: string
  providers: string[]           // list of provider type strings e.g. ["telegram"]
  subscription_status: string | null
  subscription_expires_at: string | null
  remnawave_uuid: string | null
  subscription_conflict: boolean
  created_at: string
}

export interface PaginatedUsers {
  items: UserAdminListItem[]
  total: number
  page: number
  per_page: number
}

export interface AdminSubscriptionInfo {
  type: string
  status: string
  started_at: string
  expires_at: string
  traffic_limit_gb: number | null
  synced_at: string | null
}

export interface AdminTransactionItem {
  id: string
  type: string
  status: string
  amount_rub: number | null
  days_added: number | null
  description: string | null
  created_at: string
  completed_at: string | null
}

export interface UserAdminDetail {
  id: string
  display_name: string
  avatar_url: string | null
  is_admin: boolean
  has_made_payment: boolean
  subscription_conflict: boolean
  remnawave_uuid: string | null
  created_at: string
  last_seen_at: string
  providers: AdminProviderInfo[]
  subscription: AdminSubscriptionInfo | null
  recent_transactions: AdminTransactionItem[]
}

export interface ConflictResolveRequest {
  remnawave_uuid: string
}

export interface SyncAllResponse {
  task_id: string
}

// Backend fields: status, total, done (int), errors (int count)
export interface SyncStatusResponse {
  status: 'running' | 'completed' | 'failed' | 'timed_out'
  total: number
  done: number
  errors: number
}

export interface PlanAdminItem {
  id: string
  name: string
  label: string
  duration_days: number
  price_rub: number
  new_user_price_rub: number | null
  is_active: boolean
  sort_order: number
}

export interface PlanAdminUpdateRequest {
  price_rub?: number
  new_user_price_rub?: number | null
  duration_days?: number
  label?: string
  is_active?: boolean
}

export interface PromoCodeAdminItem {
  id: string
  code: string
  type: 'discount_percent' | 'bonus_days'
  value: number
  max_uses: number | null
  used_count: number
  valid_until: string | null
  is_active: boolean
  created_at: string
}

export interface PromoCodeCreateRequest {
  code: string
  type: 'discount_percent' | 'bonus_days'
  value: number
  max_uses?: number | null
  valid_until?: string | null
}

export interface ArticleAdminListItem {
  id: string
  slug: string
  title: string
  is_published: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface ArticleAdminDetail extends ArticleAdminListItem {
  content: string
  preview_image_url: string | null
}

export interface ArticleAdminCreateRequest {
  slug: string
  title: string
  content: string
  preview_image_url?: string | null
  sort_order?: number
}

export interface ArticleAdminUpdateRequest {
  slug?: string
  title?: string
  content?: string
  preview_image_url?: string | null
  sort_order?: number
}

export interface SettingAdminItem {
  key: string
  value: string | null
  is_sensitive: boolean
  updated_at: string
}

export interface SupportMessageAdminItem {
  id: string
  user_id: string
  display_name: string
  message: string
  created_at: string
}

// Note: support-messages endpoint returns a plain list (no pagination wrapper).
// Use ?skip=N&limit=50 params.
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat: add admin TypeScript types to api.ts"
```

---

## Task 2: AdminRoute + AdminLayout Components

**Files:**
- Create: `frontend/src/components/AdminRoute.tsx`
- Create: `frontend/src/components/AdminLayout.tsx`

- [ ] **Step 1: Create `AdminRoute.tsx`**

```tsx
// frontend/src/components/AdminRoute.tsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export default function AdminRoute() {
  const { isAuthenticated, isLoading, isAdmin } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (!isAdmin) return <Navigate to="/" replace />

  return <Outlet />
}
```

- [ ] **Step 2: Create `AdminLayout.tsx`**

```tsx
// frontend/src/components/AdminLayout.tsx
import { Outlet, NavLink, Link } from 'react-router-dom'
import {
  Users, RefreshCw, CreditCard, Tag, BookOpen, Settings, MessageSquare,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'

const ADMIN_NAV = [
  { to: '/admin/users', label: 'Пользователи', icon: Users },
  { to: '/admin/sync', label: 'Синхронизация', icon: RefreshCw },
  { to: '/admin/plans', label: 'Тарифы', icon: CreditCard },
  { to: '/admin/promo-codes', label: 'Промокоды', icon: Tag },
  { to: '/admin/articles', label: 'Статьи', icon: BookOpen },
  { to: '/admin/settings', label: 'Настройки', icon: Settings },
  { to: '/admin/support-messages', label: 'Сообщения', icon: MessageSquare },
] as const

export default function AdminLayout() {
  const { user } = useAuth()

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-[220px] flex-col border-r border-border-neutral bg-surface px-4 py-6 shrink-0">
        <div className="mb-1 px-3">
          <span className="text-lg font-bold bg-gradient-to-r from-accent to-accent-hover bg-clip-text text-transparent">
            Skavellion
          </span>
        </div>
        <div className="mb-6 px-3">
          <span className="text-xs text-text-muted">Панель администратора</span>
        </div>
        <nav className="flex flex-col gap-1 flex-1">
          {ADMIN_NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-input px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-accent/10 text-accent'
                    : 'text-text-secondary hover:bg-white/5 hover:text-text-primary',
                )
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <Link
          to="/"
          className="mt-2 flex items-center gap-2 rounded-input px-3 py-2 text-xs text-text-muted hover:text-text-primary transition-colors"
        >
          ← На сайт
        </Link>
        {user && (
          <div className="mt-2 flex items-center gap-2 rounded-input px-3 py-2 bg-white/5">
            <div className="h-7 w-7 rounded-full bg-accent/20 flex items-center justify-center text-xs font-medium text-accent">
              {user.display_name[0].toUpperCase()}
            </div>
            <span className="text-xs text-text-secondary truncate">{user.display_name}</span>
          </div>
        )}
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 inset-x-0 z-50 border-b border-border-neutral bg-surface px-4 py-3 flex items-center gap-3 overflow-x-auto">
        {ADMIN_NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-1.5 shrink-0 text-xs font-medium px-2 py-1 rounded-input transition-colors',
                isActive ? 'text-accent bg-accent/10' : 'text-text-muted',
              )
            }
          >
            <Icon size={14} />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>

      {/* Main content */}
      <main className="flex-1 overflow-auto pt-14 md:pt-0 pb-4">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 3: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AdminRoute.tsx frontend/src/components/AdminLayout.tsx
git commit -m "feat: add AdminRoute guard and AdminLayout sidebar"
```

---

## Task 3: Wire Up Admin Routes in App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update `App.tsx`**

Replace the entire file:

```tsx
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/Layout'
import ProtectedRoute from '@/components/ProtectedRoute'
import AdminRoute from '@/components/AdminRoute'
import AdminLayout from '@/components/AdminLayout'
import LoginPage from '@/pages/LoginPage'
import HomePage from '@/pages/HomePage'
import SubscriptionPage from '@/pages/SubscriptionPage'
import InstallPage from '@/pages/InstallPage'
import DocsPage from '@/pages/DocsPage'
import DocsArticlePage from '@/pages/DocsArticlePage'
import SupportPage from '@/pages/SupportPage'
import ProfilePage from '@/pages/ProfilePage'
import NotFoundPage from '@/pages/NotFoundPage'
import AdminUsersPage from '@/pages/admin/AdminUsersPage'
import AdminUserDetailPage from '@/pages/admin/AdminUserDetailPage'
import AdminSyncPage from '@/pages/admin/AdminSyncPage'
import AdminPlansPage from '@/pages/admin/AdminPlansPage'
import AdminPromoCodesPage from '@/pages/admin/AdminPromoCodesPage'
import AdminArticlesPage from '@/pages/admin/AdminArticlesPage'
import AdminArticleEditPage from '@/pages/admin/AdminArticleEditPage'
import AdminSettingsPage from '@/pages/admin/AdminSettingsPage'
import AdminSupportMessagesPage from '@/pages/admin/AdminSupportMessagesPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        {/* Admin routes */}
        <Route element={<AdminRoute />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />
            <Route path="/admin/users/:id" element={<AdminUserDetailPage />} />
            <Route path="/admin/sync" element={<AdminSyncPage />} />
            <Route path="/admin/plans" element={<AdminPlansPage />} />
            <Route path="/admin/promo-codes" element={<AdminPromoCodesPage />} />
            <Route path="/admin/articles" element={<AdminArticlesPage />} />
            <Route path="/admin/articles/new" element={<AdminArticleEditPage />} />
            <Route path="/admin/articles/:id/edit" element={<AdminArticleEditPage />} />
            <Route path="/admin/settings" element={<AdminSettingsPage />} />
            <Route path="/admin/support-messages" element={<AdminSupportMessagesPage />} />
          </Route>
        </Route>

        {/* User routes */}
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

> **Note:** This step will fail type-check until all 9 admin page files are created. Create placeholder files first (see step 2), then fill them in subsequent tasks.

- [ ] **Step 2: Create placeholder admin pages (all stubs)**

Create the directory and stub each file so App.tsx compiles:

```bash
mkdir -p frontend/src/pages/admin
```

For each of these 9 files, create a minimal placeholder:

**`frontend/src/pages/admin/AdminUsersPage.tsx`**
```tsx
export default function AdminUsersPage() { return <div className="p-6"><h1 className="text-xl font-bold text-text-primary">Пользователи</h1></div> }
```

**`frontend/src/pages/admin/AdminUserDetailPage.tsx`**
```tsx
export default function AdminUserDetailPage() { return <div className="p-6"><h1 className="text-xl font-bold text-text-primary">Пользователь</h1></div> }
```

**`frontend/src/pages/admin/AdminSyncPage.tsx`**
```tsx
export default function AdminSyncPage() { return <div className="p-6"><h1 className="text-xl font-bold text-text-primary">Синхронизация</h1></div> }
```

**`frontend/src/pages/admin/AdminPlansPage.tsx`**
```tsx
export default function AdminPlansPage() { return <div className="p-6"><h1 className="text-xl font-bold text-text-primary">Тарифы</h1></div> }
```

**`frontend/src/pages/admin/AdminPromoCodesPage.tsx`**
```tsx
export default function AdminPromoCodesPage() { return <div className="p-6"><h1 className="text-xl font-bold text-text-primary">Промокоды</h1></div> }
```

**`frontend/src/pages/admin/AdminArticlesPage.tsx`**
```tsx
export default function AdminArticlesPage() { return <div className="p-6"><h1 className="text-xl font-bold text-text-primary">Статьи</h1></div> }
```

**`frontend/src/pages/admin/AdminArticleEditPage.tsx`**
```tsx
export default function AdminArticleEditPage() { return <div className="p-6"><h1 className="text-xl font-bold text-text-primary">Редактор статьи</h1></div> }
```

**`frontend/src/pages/admin/AdminSettingsPage.tsx`**
```tsx
export default function AdminSettingsPage() { return <div className="p-6"><h1 className="text-xl font-bold text-text-primary">Настройки</h1></div> }
```

**`frontend/src/pages/admin/AdminSupportMessagesPage.tsx`**
```tsx
export default function AdminSupportMessagesPage() { return <div className="p-6"><h1 className="text-xl font-bold text-text-primary">Сообщения поддержки</h1></div> }
```

- [ ] **Step 3: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/admin/
git commit -m "feat: wire up /admin/* routes with placeholder pages"
```

---

## Task 4: AdminUsersPage

**Files:**
- Modify: `frontend/src/pages/admin/AdminUsersPage.tsx`

- [ ] **Step 1: Implement AdminUsersPage**

```tsx
// frontend/src/pages/admin/AdminUsersPage.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search, AlertTriangle } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { PaginatedUsers } from '@/types/api'

export default function AdminUsersPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery<PaginatedUsers>({
    queryKey: ['admin-users', page, search],
    queryFn: () =>
      api.get<PaginatedUsers>(
        `/api/admin/users?page=${page}&per_page=20&search=${encodeURIComponent(search)}`,
      ),
    staleTime: 30_000,
  })

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Пользователи</h1>

      <div className="relative mb-4">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
        <input
          type="text"
          placeholder="Поиск по имени..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          className="w-full rounded-input bg-surface border border-border-neutral pl-9 pr-4 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400">
          {error instanceof ApiError ? error.detail : 'Ошибка загрузки'}
        </p>
      )}

      {data && (
        <>
          <div className="flex flex-col gap-1">
            {data.items.length === 0 && (
              <p className="text-sm text-text-muted text-center py-8">Пользователи не найдены</p>
            )}
            {data.items.map((user) => (
              <button
                key={user.id}
                onClick={() => navigate(`/admin/users/${user.id}`)}
                className="flex items-center gap-3 rounded-input bg-surface border border-border-neutral px-4 py-3 text-left hover:border-border-accent transition-colors w-full"
              >
                <div className="h-8 w-8 rounded-full bg-accent/20 flex items-center justify-center text-xs font-bold text-accent shrink-0">
                  {user.display_name[0]?.toUpperCase() ?? '?'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-text-primary truncate">
                      {user.display_name}
                    </span>
                    {user.subscription_conflict && (
                      <span className="flex items-center gap-1 text-xs bg-red-500/15 text-red-400 px-1.5 py-0.5 rounded">
                        <AlertTriangle size={10} />
                        конфликт
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                    <span className="text-xs text-text-muted">
                      {user.providers.join(', ')}
                    </span>
                    {user.subscription_status && (
                      <span
                        className={`text-xs ${
                          user.subscription_status === 'active'
                            ? 'text-green-400'
                            : 'text-text-muted'
                        }`}
                      >
                        {user.subscription_status === 'active'
                          ? 'активна'
                          : user.subscription_status === 'expired'
                          ? 'истекла'
                          : user.subscription_status}
                      </span>
                    )}
                    {user.subscription_expires_at && (
                      <span className="text-xs text-text-muted">
                        до {new Date(user.subscription_expires_at).toLocaleDateString('ru-RU')}
                      </span>
                    )}
                  </div>
                </div>
                <span className="text-xs text-text-muted shrink-0">
                  {new Date(user.created_at).toLocaleDateString('ru-RU')}
                </span>
              </button>
            ))}
          </div>

          {data.total > 20 && (
            <div className="flex items-center justify-between mt-4">
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
                className="text-sm text-accent disabled:text-text-muted disabled:cursor-not-allowed"
              >
                ← Назад
              </button>
              <span className="text-xs text-text-muted">
                {(page - 1) * 20 + 1}–{Math.min(page * 20, data.total)} из {data.total}
              </span>
              <button
                disabled={page * 20 >= data.total}
                onClick={() => setPage((p) => p + 1)}
                className="text-sm text-accent disabled:text-text-muted disabled:cursor-not-allowed"
              >
                Вперёд →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminUsersPage.tsx
git commit -m "feat: implement AdminUsersPage with search and pagination"
```

---

## Task 5: AdminUserDetailPage

**Files:**
- Modify: `frontend/src/pages/admin/AdminUserDetailPage.tsx`

- [ ] **Step 1: Implement AdminUserDetailPage**

```tsx
// frontend/src/pages/admin/AdminUserDetailPage.tsx
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { UserAdminDetail, ConflictResolveRequest } from '@/types/api'

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [syncMsg, setSyncMsg] = useState<string | null>(null)
  const [resolveMsg, setResolveMsg] = useState<string | null>(null)
  const [resolveUuid, setResolveUuid] = useState('')

  const { data: user, isLoading, error } = useQuery<UserAdminDetail>({
    queryKey: ['admin-user', id],
    queryFn: () => api.get<UserAdminDetail>(`/api/admin/users/${id}`),
    enabled: !!id,
  })

  const syncMutation = useMutation({
    mutationFn: () => api.post(`/api/admin/users/${id}/sync`, {}),
    onSuccess: () => {
      setSyncMsg('Синхронизация выполнена')
      queryClient.invalidateQueries({ queryKey: ['admin-user', id] })
      setTimeout(() => setSyncMsg(null), 3000)
    },
  })

  const resolveMutation = useMutation({
    mutationFn: (data: ConflictResolveRequest) =>
      api.post(`/api/admin/users/${id}/resolve-conflict`, data),
    onSuccess: () => {
      setResolveMsg('Конфликт разрешён')
      queryClient.invalidateQueries({ queryKey: ['admin-user', id] })
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setTimeout(() => setResolveMsg(null), 3000)
    },
  })

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

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <button
        onClick={() => navigate('/admin/users')}
        className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary mb-5 transition-colors"
      >
        <ArrowLeft size={15} /> Назад
      </button>

      <div className="flex items-start justify-between mb-5 gap-3">
        <div>
          <h1 className="text-xl font-bold text-text-primary">{user.display_name}</h1>
          <p className="text-xs text-text-muted mt-0.5">
            {user.providers.map((p) => p.provider_username ?? p.provider).join(' · ')}
          </p>
        </div>
        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-white/5 text-sm text-text-secondary hover:text-text-primary disabled:opacity-50 transition-colors"
        >
          <RefreshCw size={14} className={syncMutation.isPending ? 'animate-spin' : ''} />
          Синхронизировать
        </button>
      </div>

      {syncMsg && (
        <div className="flex items-center gap-2 text-xs text-green-400 mb-3">
          <CheckCircle size={13} /> {syncMsg}
        </div>
      )}

      {user.subscription_conflict && (
        <div className="rounded-input bg-red-500/10 border border-red-500/20 px-4 py-3 mb-4">
          <div className="flex items-center gap-2 text-sm text-red-400 mb-2">
            <AlertTriangle size={15} />
            Конфликт подписки — укажите Remnawave UUID для сохранения
          </div>
          <p className="text-xs text-text-muted mb-2">
            Текущий: <span className="font-mono">{user.remnawave_uuid ?? '—'}</span>
          </p>
          <div className="flex gap-2">
            <input
              value={resolveUuid}
              onChange={(e) => setResolveUuid(e.target.value)}
              placeholder="UUID для сохранения"
              className="flex-1 rounded-input bg-background border border-red-500/30 px-2.5 py-1.5 text-xs text-text-primary font-mono focus:outline-none focus:border-red-400"
            />
            <button
              onClick={() => resolveMutation.mutate({ remnawave_uuid: resolveUuid })}
              disabled={resolveMutation.isPending || !resolveUuid.trim()}
              className="text-xs px-2.5 py-1.5 rounded-input bg-red-500/20 text-red-300 hover:bg-red-500/30 disabled:opacity-50 transition-colors"
            >
              Разрешить
            </button>
          </div>
        </div>
      )}

      {resolveMsg && (
        <div className="flex items-center gap-2 text-xs text-green-400 mb-3">
          <CheckCircle size={13} /> {resolveMsg}
        </div>
      )}

      {/* Info */}
      <div className="rounded-card bg-surface border border-border-neutral p-4 mb-4">
        <h2 className="text-sm font-semibold text-text-primary mb-3">Информация</h2>
        <div className="flex flex-col gap-2">
          {[
            ['ID', user.id],
            ['Remnawave UUID', user.remnawave_uuid ?? '—'],
            ['Оплачивал', user.has_made_payment ? 'Да' : 'Нет'],
            ['Создан', new Date(user.created_at).toLocaleString('ru-RU')],
            ['Последняя активность', new Date(user.last_seen_at).toLocaleString('ru-RU')],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-3 text-sm">
              <span className="text-text-muted shrink-0">{label}</span>
              <span className="text-text-secondary text-right break-all">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Subscription */}
      {user.subscription && (
        <div className="rounded-card bg-surface border border-border-neutral p-4 mb-4">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Подписка</h2>
          <div className="flex flex-col gap-2">
            {[
              ['Тип', user.subscription.type === 'trial' ? 'Пробная' : 'Платная'],
              ['Статус', user.subscription.status],
              ['Истекает', new Date(user.subscription.expires_at).toLocaleDateString('ru-RU')],
              ['Осталось дней', String(user.subscription.days_remaining)],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-3 text-sm">
                <span className="text-text-muted">{label}</span>
                <span className="text-text-secondary">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Transactions */}
      {user.recent_transactions.length > 0 && (
        <div className="rounded-card bg-surface border border-border-neutral p-4">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Последние транзакции</h2>
          <div className="flex flex-col gap-1">
            {user.recent_transactions.map((tx) => (
              <div
                key={tx.id}
                className="flex items-center justify-between gap-3 py-1.5 border-b border-border-neutral last:border-0"
              >
                <div>
                  <span className="text-xs text-text-primary">{tx.type}</span>
                  {tx.days_added && (
                    <span className="ml-2 text-xs text-text-muted">+{tx.days_added}д</span>
                  )}
                </div>
                <div className="text-right">
                  {tx.amount_rub && (
                    <span className="text-xs text-text-secondary">{tx.amount_rub} ₽</span>
                  )}
                  <span
                    className={`ml-2 text-xs ${
                      tx.status === 'completed'
                        ? 'text-green-400'
                        : tx.status === 'failed'
                        ? 'text-red-400'
                        : 'text-text-muted'
                    }`}
                  >
                    {tx.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminUserDetailPage.tsx
git commit -m "feat: implement AdminUserDetailPage with sync and conflict resolution"
```

---

## Task 6: AdminSyncPage

**Files:**
- Modify: `frontend/src/pages/admin/AdminSyncPage.tsx`

- [ ] **Step 1: Implement AdminSyncPage**

```tsx
// frontend/src/pages/admin/AdminSyncPage.tsx
import { useState, useEffect, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { RefreshCw, CheckCircle, XCircle } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { SyncAllResponse, SyncStatusResponse } from '@/types/api'

export default function AdminSyncPage() {
  const [status, setStatus] = useState<SyncStatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Clean up polling on unmount
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  function startPolling(taskId: string) {
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.get<SyncStatusResponse>(`/api/admin/sync/status/${taskId}`)
        setStatus(s)
        if (s.status === 'completed' || s.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current)
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current)
      }
    }, 2000)
  }

  const syncMutation = useMutation({
    mutationFn: () => api.post<SyncAllResponse>('/api/admin/sync/all', {}),
    onMutate: () => {
      setStatus(null)
      setError(null)
    },
    onSuccess: (data) => {
      setStatus({ status: 'running', total: 0, done: 0, errors: 0 })
      startPolling(data.task_id)
    },
    onError: (e) => {
      setError(e instanceof ApiError ? e.detail : 'Ошибка запуска синхронизации')
    },
  })

  const isRunning = status?.status === 'running'
  const progressPct =
    status && status.total > 0 ? Math.round((status.done / status.total) * 100) : 0

  return (
    <div className="p-4 md:p-6 max-w-xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-2">Синхронизация</h1>
      <p className="text-sm text-text-muted mb-6">
        Принудительно синхронизирует всех пользователей с Remnawave.
      </p>

      <button
        onClick={() => syncMutation.mutate()}
        disabled={syncMutation.isPending || isRunning}
        className="flex items-center gap-2 px-5 py-2.5 rounded-input bg-accent text-background text-sm font-medium disabled:opacity-50 hover:bg-accent-hover transition-colors"
      >
        <RefreshCw size={15} className={isRunning ? 'animate-spin' : ''} />
        {isRunning ? 'Синхронизация...' : 'Запустить синхронизацию'}
      </button>

      {error && <p className="mt-3 text-xs text-red-400">{error}</p>}

      {status && (
        <div className="mt-6 rounded-card bg-surface border border-border-neutral p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-text-primary">
              {status.status === 'completed'
                ? 'Завершено'
                : status.status === 'failed'
                ? 'Ошибка'
                : status.status === 'running'
                ? 'Выполняется...'
                : 'Ожидание...'}
            </span>
            {status.status === 'completed' && <CheckCircle size={16} className="text-green-400" />}
            {status.status === 'failed' && <XCircle size={16} className="text-red-400" />}
          </div>

          {status.total > 0 && (
            <>
              <div className="w-full bg-white/5 rounded-full h-2 mb-2">
                <div
                  className="bg-accent h-2 rounded-full transition-all duration-500"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <p className="text-xs text-text-muted">
                {status.done} / {status.total} пользователей ({progressPct}%)
              </p>
            </>
          )}

          {status.errors > 0 && (
            <p className="mt-3 text-xs text-red-400">
              Ошибок: {status.errors}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminSyncPage.tsx
git commit -m "feat: implement AdminSyncPage with progress polling"
```

---

## Task 7: AdminPlansPage

**Files:**
- Modify: `frontend/src/pages/admin/AdminPlansPage.tsx`

- [ ] **Step 1: Implement AdminPlansPage**

Each plan row has inline editing via local state. Submit sends PATCH.

```tsx
// frontend/src/pages/admin/AdminPlansPage.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Pencil, X, Check } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { PlanAdminItem, PlanAdminUpdateRequest } from '@/types/api'

function PlanRow({ plan }: { plan: PlanAdminItem }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<PlanAdminUpdateRequest>({
    price_rub: plan.price_rub,
    new_user_price_rub: plan.new_user_price_rub ?? undefined,
    duration_days: plan.duration_days,
    label: plan.label,
    is_active: plan.is_active,
  })
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (data: PlanAdminUpdateRequest) =>
      api.patch<PlanAdminItem>(`/api/admin/plans/${plan.id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-plans'] })
      setEditing(false)
      setSaveError(null)
    },
    onError: (e) => {
      setSaveError(e instanceof ApiError ? e.detail : 'Ошибка сохранения')
    },
  })

  if (!editing) {
    return (
      <div className="flex items-center gap-3 rounded-input bg-surface border border-border-neutral px-4 py-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-primary">{plan.name}</span>
            {plan.label && (
              <span className="text-xs bg-accent/10 text-accent px-1.5 py-0.5 rounded">{plan.label}</span>
            )}
            {!plan.is_active && (
              <span className="text-xs bg-white/5 text-text-muted px-1.5 py-0.5 rounded">неактивен</span>
            )}
          </div>
          <div className="flex items-center gap-4 mt-0.5 text-xs text-text-muted">
            <span>{plan.duration_days}д</span>
            <span>{plan.price_rub} ₽</span>
            {plan.new_user_price_rub != null && (
              <span>{plan.new_user_price_rub} ₽ (новый)</span>
            )}
          </div>
        </div>
        <button
          onClick={() => setEditing(true)}
          className="p-1.5 rounded-input text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
        >
          <Pencil size={14} />
        </button>
      </div>
    )
  }

  return (
    <div className="rounded-input bg-surface border border-border-accent px-4 py-3">
      <div className="grid grid-cols-2 gap-3 mb-3">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Метка</span>
          <input
            value={form.label ?? ''}
            onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Дней</span>
          <input
            type="number"
            value={form.duration_days ?? ''}
            onChange={(e) => setForm((f) => ({ ...f, duration_days: Number(e.target.value) }))}
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Цена (₽)</span>
          <input
            type="number"
            value={form.price_rub ?? ''}
            onChange={(e) => setForm((f) => ({ ...f, price_rub: Number(e.target.value) }))}
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Цена новому (₽)</span>
          <input
            type="number"
            value={form.new_user_price_rub ?? ''}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                new_user_price_rub: e.target.value === '' ? null : Number(e.target.value),
              }))
            }
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
      </div>
      <label className="flex items-center gap-2 mb-3 cursor-pointer">
        <input
          type="checkbox"
          checked={form.is_active ?? false}
          onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
          className="rounded accent-cyan-500"
        />
        <span className="text-sm text-text-secondary">Активен</span>
      </label>
      {saveError && <p className="text-xs text-red-400 mb-2">{saveError}</p>}
      <div className="flex gap-2">
        <button
          onClick={() => mutation.mutate(form)}
          disabled={mutation.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-accent text-background text-xs font-medium disabled:opacity-50 transition-colors"
        >
          <Check size={13} /> Сохранить
        </button>
        <button
          onClick={() => { setEditing(false); setSaveError(null) }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-white/5 text-text-secondary text-xs hover:text-text-primary transition-colors"
        >
          <X size={13} /> Отмена
        </button>
      </div>
    </div>
  )
}

export default function AdminPlansPage() {
  const { data: plans, isLoading, error } = useQuery<PlanAdminItem[]>({
    queryKey: ['admin-plans'],
    queryFn: () => api.get<PlanAdminItem[]>('/api/admin/plans'),
    staleTime: 60_000,
  })

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Тарифы</h1>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400">
          {error instanceof ApiError ? error.detail : 'Ошибка загрузки'}
        </p>
      )}

      <div className="flex flex-col gap-2">
        {plans?.map((plan) => <PlanRow key={plan.id} plan={plan} />)}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminPlansPage.tsx
git commit -m "feat: implement AdminPlansPage with inline editing"
```

---

## Task 8: AdminPromoCodesPage

**Files:**
- Modify: `frontend/src/pages/admin/AdminPromoCodesPage.tsx`

- [ ] **Step 1: Implement AdminPromoCodesPage**

```tsx
// frontend/src/pages/admin/AdminPromoCodesPage.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { PromoCodeAdminItem, PromoCodeCreateRequest } from '@/types/api'

const EMPTY_FORM: PromoCodeCreateRequest = {
  code: '',
  type: 'bonus_days',
  value: 7,
  max_uses: null,
  valid_until: null,
}

export default function AdminPromoCodesPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<PromoCodeCreateRequest>(EMPTY_FORM)
  const [createError, setCreateError] = useState<string | null>(null)

  const { data: codes, isLoading, error } = useQuery<PromoCodeAdminItem[]>({
    queryKey: ['admin-promo-codes'],
    queryFn: () => api.get<PromoCodeAdminItem[]>('/api/admin/promo-codes'),
    staleTime: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: (data: PromoCodeCreateRequest) =>
      api.post<PromoCodeAdminItem>('/api/admin/promo-codes', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-promo-codes'] })
      setForm(EMPTY_FORM)
      setShowForm(false)
      setCreateError(null)
    },
    onError: (e) => {
      setCreateError(e instanceof ApiError ? e.detail : 'Ошибка создания')
    },
  })

  const toggleMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/api/admin/promo-codes/${id}/toggle`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-promo-codes'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/admin/promo-codes/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-promo-codes'] }),
  })

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-text-primary">Промокоды</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-accent text-background text-xs font-medium hover:bg-accent-hover transition-colors"
        >
          <Plus size={14} /> Создать
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-card bg-surface border border-border-accent p-4 mb-5">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Новый промокод</h2>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <label className="col-span-2 flex flex-col gap-1">
              <span className="text-xs text-text-muted">Код</span>
              <input
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                placeholder="SUMMER2026"
                className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-text-muted">Тип</span>
              <select
                value={form.type}
                onChange={(e) =>
                  setForm((f) => ({ ...f, type: e.target.value as PromoCodeCreateRequest['type'] }))
                }
                className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              >
                <option value="bonus_days">Бонусные дни</option>
                <option value="discount_percent">Скидка %</option>
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-text-muted">
                {form.type === 'bonus_days' ? 'Дней' : 'Процент'}
              </span>
              <input
                type="number"
                value={form.value}
                onChange={(e) => setForm((f) => ({ ...f, value: Number(e.target.value) }))}
                className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-text-muted">Макс. использований</span>
              <input
                type="number"
                value={form.max_uses ?? ''}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    max_uses: e.target.value === '' ? null : Number(e.target.value),
                  }))
                }
                placeholder="∞"
                className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-text-muted">Действует до</span>
              <input
                type="date"
                value={form.valid_until ?? ''}
                onChange={(e) =>
                  setForm((f) => ({ ...f, valid_until: e.target.value || null }))
                }
                className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </label>
          </div>
          {createError && <p className="text-xs text-red-400 mb-2">{createError}</p>}
          <div className="flex gap-2">
            <button
              onClick={() => createMutation.mutate(form)}
              disabled={createMutation.isPending || !form.code}
              className="px-4 py-1.5 rounded-input bg-accent text-background text-xs font-medium disabled:opacity-50 transition-colors"
            >
              Создать
            </button>
            <button
              onClick={() => { setShowForm(false); setCreateError(null); setForm(EMPTY_FORM) }}
              className="px-4 py-1.5 rounded-input bg-white/5 text-text-secondary text-xs hover:text-text-primary transition-colors"
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400">
          {error instanceof ApiError ? error.detail : 'Ошибка загрузки'}
        </p>
      )}

      <div className="flex flex-col gap-1">
        {codes?.map((code) => (
          <div
            key={code.id}
            className="flex items-center gap-3 rounded-input bg-surface border border-border-neutral px-4 py-3"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-mono font-medium text-text-primary">{code.code}</span>
                {!code.is_active && (
                  <span className="text-xs bg-white/5 text-text-muted px-1.5 py-0.5 rounded">неактивен</span>
                )}
              </div>
              <div className="flex items-center gap-3 mt-0.5 text-xs text-text-muted flex-wrap">
                <span>
                  {code.type === 'bonus_days' ? `+${code.value}д` : `${code.value}%`}
                </span>
                <span>
                  использований: {code.used_count}{code.max_uses != null ? `/${code.max_uses}` : ''}
                </span>
                {code.valid_until && (
                  <span>до {new Date(code.valid_until).toLocaleDateString('ru-RU')}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() => toggleMutation.mutate(code.id)}
                disabled={toggleMutation.isPending}
                title={code.is_active ? 'Отключить' : 'Включить'}
                className="p-1.5 rounded-input text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
              >
                {code.is_active ? <ToggleRight size={16} className="text-accent" /> : <ToggleLeft size={16} />}
              </button>
              <button
                onClick={() => {
                  if (confirm(`Удалить промокод ${code.code}?`)) deleteMutation.mutate(code.id)
                }}
                disabled={deleteMutation.isPending}
                className="p-1.5 rounded-input text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
        {codes?.length === 0 && (
          <p className="text-sm text-text-muted text-center py-8">Промокоды не созданы</p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminPromoCodesPage.tsx
git commit -m "feat: implement AdminPromoCodesPage with create, toggle, delete"
```

---

## Task 9: AdminArticlesPage

**Files:**
- Modify: `frontend/src/pages/admin/AdminArticlesPage.tsx`

- [ ] **Step 1: Implement AdminArticlesPage**

```tsx
// frontend/src/pages/admin/AdminArticlesPage.tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, Pencil, Trash2, Eye, EyeOff } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { ArticleAdminListItem } from '@/types/api'

export default function AdminArticlesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: articles, isLoading, error } = useQuery<ArticleAdminListItem[]>({
    queryKey: ['admin-articles'],
    queryFn: () => api.get<ArticleAdminListItem[]>('/api/admin/articles'),
    staleTime: 30_000,
  })

  const publishMutation = useMutation({
    mutationFn: ({ id, publish }: { id: string; publish: boolean }) =>
      api.post(`/api/admin/articles/${id}/${publish ? 'publish' : 'unpublish'}`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-articles'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/admin/articles/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-articles'] }),
  })

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-text-primary">Статьи</h1>
        <button
          onClick={() => navigate('/admin/articles/new')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-accent text-background text-xs font-medium hover:bg-accent-hover transition-colors"
        >
          <Plus size={14} /> Создать
        </button>
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400">
          {error instanceof ApiError ? error.detail : 'Ошибка загрузки'}
        </p>
      )}

      <div className="flex flex-col gap-1">
        {articles?.map((article) => (
          <div
            key={article.id}
            className="flex items-center gap-3 rounded-input bg-surface border border-border-neutral px-4 py-3"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-text-primary truncate">
                  {article.title}
                </span>
                {!article.is_published && (
                  <span className="text-xs bg-white/5 text-text-muted px-1.5 py-0.5 rounded shrink-0">
                    черновик
                  </span>
                )}
              </div>
              <span className="text-xs text-text-muted font-mono">{article.slug}</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() =>
                  publishMutation.mutate({ id: article.id, publish: !article.is_published })
                }
                disabled={publishMutation.isPending}
                title={article.is_published ? 'Снять с публикации' : 'Опубликовать'}
                className="p-1.5 rounded-input text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
              >
                {article.is_published ? (
                  <EyeOff size={14} />
                ) : (
                  <Eye size={14} className="text-accent" />
                )}
              </button>
              <button
                onClick={() => navigate(`/admin/articles/${article.id}/edit`)}
                className="p-1.5 rounded-input text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={() => {
                  if (confirm(`Удалить статью "${article.title}"?`))
                    deleteMutation.mutate(article.id)
                }}
                disabled={deleteMutation.isPending}
                className="p-1.5 rounded-input text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
        {articles?.length === 0 && (
          <p className="text-sm text-text-muted text-center py-8">Статьи не найдены</p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminArticlesPage.tsx
git commit -m "feat: implement AdminArticlesPage with publish and delete"
```

---

## Task 10: AdminArticleEditPage

**Files:**
- Modify: `frontend/src/pages/admin/AdminArticleEditPage.tsx`

This page handles both **create** (`/admin/articles/new`, no `:id` param) and **edit** (`/admin/articles/:id/edit`).

- [ ] **Step 1: Implement AdminArticleEditPage**

```tsx
// frontend/src/pages/admin/AdminArticleEditPage.tsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowLeft, Eye, Code } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type {
  ArticleAdminDetail,
  ArticleAdminCreateRequest,
  ArticleAdminUpdateRequest,
} from '@/types/api'

export default function AdminArticleEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isNew = !id
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [preview, setPreview] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [form, setForm] = useState({
    slug: '',
    title: '',
    content: '',
    preview_image_url: '',
    sort_order: 0,
  })

  const { data: existing, isLoading } = useQuery<ArticleAdminDetail>({
    queryKey: ['admin-article', id],
    queryFn: () => api.get<ArticleAdminDetail>(`/api/admin/articles/${id}`),
    enabled: !isNew,
  })

  useEffect(() => {
    if (existing) {
      setForm({
        slug: existing.slug,
        title: existing.title,
        content: existing.content,
        preview_image_url: existing.preview_image_url ?? '',
        sort_order: existing.sort_order,
      })
    }
  }, [existing])

  const createMutation = useMutation({
    mutationFn: (data: ArticleAdminCreateRequest) =>
      api.post<ArticleAdminDetail>('/api/admin/articles', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-articles'] })
      navigate('/admin/articles')
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка создания'),
  })

  const updateMutation = useMutation({
    mutationFn: (data: ArticleAdminUpdateRequest) =>
      api.patch<ArticleAdminDetail>(`/api/admin/articles/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-articles'] })
      queryClient.invalidateQueries({ queryKey: ['admin-article', id] })
      navigate('/admin/articles')
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка сохранения'),
  })

  function handleSave() {
    setSaveError(null)
    const payload = {
      slug: form.slug,
      title: form.title,
      content: form.content,
      preview_image_url: form.preview_image_url || null,
      sort_order: form.sort_order,
    }
    if (isNew) {
      createMutation.mutate(payload)
    } else {
      updateMutation.mutate(payload)
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  if (!isNew && isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-5 gap-3">
        <button
          onClick={() => navigate('/admin/articles')}
          className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft size={15} /> Назад
        </button>
        <h1 className="text-lg font-bold text-text-primary">
          {isNew ? 'Новая статья' : 'Редактировать статью'}
        </h1>
        <button
          onClick={handleSave}
          disabled={isSaving || !form.slug || !form.title || !form.content}
          className="px-4 py-1.5 rounded-input bg-accent text-background text-sm font-medium disabled:opacity-50 hover:bg-accent-hover transition-colors"
        >
          {isSaving ? 'Сохранение...' : 'Сохранить'}
        </button>
      </div>

      {/* Meta fields */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Slug (URL)</span>
          <input
            value={form.slug}
            onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
            placeholder="kak-podklyuchitsya"
            className="rounded-input bg-surface border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent font-mono"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Порядок сортировки</span>
          <input
            type="number"
            value={form.sort_order}
            onChange={(e) => setForm((f) => ({ ...f, sort_order: Number(e.target.value) }))}
            className="rounded-input bg-surface border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="col-span-2 flex flex-col gap-1">
          <span className="text-xs text-text-muted">Заголовок</span>
          <input
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            placeholder="Как подключиться к туннелю"
            className="rounded-input bg-surface border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="col-span-2 flex flex-col gap-1">
          <span className="text-xs text-text-muted">URL превью-изображения</span>
          <input
            value={form.preview_image_url}
            onChange={(e) => setForm((f) => ({ ...f, preview_image_url: e.target.value }))}
            placeholder="https://..."
            className="rounded-input bg-surface border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
      </div>

      {/* Editor / Preview toggle */}
      <div className="flex items-center gap-2 mb-2">
        <button
          onClick={() => setPreview(false)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-input text-xs transition-colors ${
            !preview ? 'bg-accent/10 text-accent' : 'text-text-muted hover:text-text-primary'
          }`}
        >
          <Code size={13} /> Редактор
        </button>
        <button
          onClick={() => setPreview(true)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-input text-xs transition-colors ${
            preview ? 'bg-accent/10 text-accent' : 'text-text-muted hover:text-text-primary'
          }`}
        >
          <Eye size={13} /> Предпросмотр
        </button>
      </div>

      {!preview ? (
        <textarea
          value={form.content}
          onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
          placeholder="# Заголовок&#10;&#10;Текст статьи в Markdown..."
          rows={24}
          className="w-full rounded-card bg-surface border border-border-neutral px-4 py-3 text-sm text-text-primary placeholder:text-text-muted font-mono focus:outline-none focus:border-accent resize-y"
        />
      ) : (
        <div className="w-full rounded-card bg-surface border border-border-neutral px-4 py-3 min-h-[400px] prose prose-invert prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{form.content || '*Контент пуст*'}</ReactMarkdown>
        </div>
      )}

      {saveError && <p className="mt-2 text-xs text-red-400">{saveError}</p>}
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminArticleEditPage.tsx
git commit -m "feat: implement AdminArticleEditPage with markdown editor and preview"
```

---

## Task 11: AdminSettingsPage

**Files:**
- Modify: `frontend/src/pages/admin/AdminSettingsPage.tsx`

- [ ] **Step 1: Implement AdminSettingsPage**

Each setting has its own "Save" button. Sensitive fields show masked value from backend and allow overwrite.

```tsx
// frontend/src/pages/admin/AdminSettingsPage.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Eye, EyeOff } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { SettingAdminItem } from '@/types/api'

function SettingRow({ setting }: { setting: SettingAdminItem }) {
  const queryClient = useQueryClient()
  const [value, setValue] = useState(setting.value ?? '')
  const [showValue, setShowValue] = useState(false)
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

  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-text-muted">{setting.key}</span>
        {setting.is_sensitive && (
          <span className="text-xs bg-yellow-500/10 text-yellow-400 px-1.5 py-0.5 rounded">
            скрытое
          </span>
        )}
      </div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type={setting.is_sensitive && !showValue ? 'password' : 'text'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={setting.is_sensitive ? '••••••••' : 'Значение'}
            className="w-full rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
          {setting.is_sensitive && (
            <button
              onClick={() => setShowValue((v) => !v)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
            >
              {showValue ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          )}
        </div>
        <button
          onClick={() => mutation.mutate(value)}
          disabled={mutation.isPending}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-input text-xs font-medium transition-colors ${
            saved
              ? 'bg-green-500/20 text-green-400'
              : 'bg-accent/10 text-accent hover:bg-accent/20'
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

export default function AdminSettingsPage() {
  const { data: settings, isLoading, error } = useQuery<SettingAdminItem[]>({
    queryKey: ['admin-settings'],
    queryFn: () => api.get<SettingAdminItem[]>('/api/admin/settings'),
    staleTime: 60_000,
  })

  // Group settings: sensitive vs regular
  const regular = settings?.filter((s) => !s.is_sensitive) ?? []
  const sensitive = settings?.filter((s) => s.is_sensitive) ?? []

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Настройки</h1>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400">
          {error instanceof ApiError ? error.detail : 'Ошибка загрузки'}
        </p>
      )}

      {regular.length > 0 && (
        <div className="mb-5">
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2 px-1">
            Основные
          </h2>
          <div className="flex flex-col gap-2">
            {regular.map((s) => <SettingRow key={s.key} setting={s} />)}
          </div>
        </div>
      )}

      {sensitive.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2 px-1">
            Секреты / токены
          </h2>
          <div className="flex flex-col gap-2">
            {sensitive.map((s) => <SettingRow key={s.key} setting={s} />)}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminSettingsPage.tsx
git commit -m "feat: implement AdminSettingsPage with per-key save and masked secrets"
```

---

## Task 12: AdminSupportMessagesPage

**Files:**
- Modify: `frontend/src/pages/admin/AdminSupportMessagesPage.tsx`

- [ ] **Step 1: Implement AdminSupportMessagesPage**

```tsx
// frontend/src/pages/admin/AdminSupportMessagesPage.tsx
// Note: endpoint returns plain list[SupportMessageAdminItem], NOT a paginated wrapper.
// Uses ?skip=N&limit=50 for load-more.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import type { SupportMessageAdminItem } from '@/types/api'

const PAGE_SIZE = 50

export default function AdminSupportMessagesPage() {
  const [skip, setSkip] = useState(0)

  const { data, isLoading, error } = useQuery<SupportMessageAdminItem[]>({
    queryKey: ['admin-support-messages', skip],
    queryFn: () =>
      api.get<SupportMessageAdminItem[]>(
        `/api/admin/support-messages?skip=${skip}&limit=${PAGE_SIZE}`,
      ),
    staleTime: 30_000,
  })

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Сообщения поддержки</h1>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400">
          {error instanceof ApiError ? error.detail : 'Ошибка загрузки'}
        </p>
      )}

      <div className="flex flex-col gap-2">
        {data?.length === 0 && (
          <p className="text-sm text-text-muted text-center py-8">Сообщений нет</p>
        )}
        {data?.map((msg) => (
          <div
            key={msg.id}
            className="rounded-card bg-surface border border-border-neutral px-4 py-3"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm font-medium text-text-primary">{msg.display_name}</span>
              <span className="text-xs text-text-muted">
                {new Date(msg.created_at).toLocaleString('ru-RU')}
              </span>
            </div>
            <p className="text-sm text-text-secondary whitespace-pre-wrap">{msg.message}</p>
          </div>
        ))}
      </div>

      {/* Load more (endpoint returns up to 50 per page) */}
      {data && data.length === PAGE_SIZE && (
        <button
          onClick={() => setSkip((s) => s + PAGE_SIZE)}
          className="mt-4 w-full py-2 rounded-input text-sm text-accent bg-surface border border-border-neutral hover:border-border-accent transition-colors"
        >
          Загрузить ещё
        </button>
      )}
      {skip > 0 && (
        <button
          onClick={() => setSkip(0)}
          className="mt-2 w-full py-1.5 rounded-input text-xs text-text-muted hover:text-text-primary transition-colors"
        >
          В начало
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/AdminSupportMessagesPage.tsx
git commit -m "feat: implement AdminSupportMessagesPage with load-more"
```

---

## Task 13: Final Build Verification

**Files:** none (verification only)

- [ ] **Step 1: Run full type-check**

```bash
cd frontend && npm run type-check
```
Expected: 0 errors

- [ ] **Step 2: Run production build**

```bash
cd frontend && npm run build
```
Expected: build succeeds, no TypeScript errors, bundle size reasonable

- [ ] **Step 3: Commit if any last fixes were needed**

```bash
git add -A
git commit -m "fix: resolve any build-time type errors in admin panel"
```

- [ ] **Step 4: Update project status memory**

Update `C:\Users\Skavellion\.claude\projects\E--Projects-vpn-custom-sub-pages\memory\project_status.md`:
- Mark Plan 10 as completed
- Note: all 10 plans complete, project is frontend-complete
- Next: deployment / Docker Compose setup (if needed)

# Plan 8: Frontend Setup — Vite + React + TypeScript + Tailwind + shadcn/ui

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the React frontend with Vite, TypeScript, Tailwind CSS, shadcn/ui components, React Router v6, TanStack Query, and an API client layer — giving all subsequent plans a working, styled, routable shell.

**Architecture:** Single-page app in `frontend/src/`. All API calls go through a thin `src/lib/api.ts` client (native `fetch` with cookie credentials). TanStack Query handles caching. React Router v6 handles routing with a layout component wrapping authenticated pages. Auth state comes from `GET /api/users/me` — if it returns 401 the user is unauthenticated.

**Tech Stack:** Node.js 20+, Vite 5, React 18, TypeScript 5, Tailwind CSS 3, shadcn/ui, Radix UI, TanStack Query v5, React Router v6, lucide-react

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Create** | `frontend/package.json` | Dependencies |
| **Create** | `frontend/vite.config.ts` | Dev server proxy `/api → backend:8000` |
| **Create** | `frontend/tsconfig.json` | TypeScript config |
| **Create** | `frontend/tsconfig.app.json` | App TypeScript config |
| **Create** | `frontend/tailwind.config.ts` | Design tokens (colors, radius) |
| **Create** | `frontend/postcss.config.js` | PostCSS for Tailwind |
| **Create** | `frontend/index.html` | HTML entry point |
| **Create** | `frontend/src/main.tsx` | React root mount |
| **Create** | `frontend/src/App.tsx` | Router + QueryClient setup |
| **Create** | `frontend/src/lib/api.ts` | Typed fetch wrapper |
| **Create** | `frontend/src/lib/queryClient.ts` | TanStack Query client |
| **Create** | `frontend/src/types/api.ts` | Shared API types |
| **Create** | `frontend/src/hooks/useAuth.ts` | `useQuery` for `/api/users/me` |
| **Create** | `frontend/src/components/Layout.tsx` | Sidebar (desktop) + bottom nav (mobile) shell |
| **Create** | `frontend/src/components/ProtectedRoute.tsx` | Redirect to /login if not authed |
| **Create** | `frontend/src/pages/LoginPage.tsx` | Login page placeholder |
| **Create** | `frontend/src/pages/HomePage.tsx` | Home page placeholder |
| **Create** | `frontend/src/pages/NotFoundPage.tsx` | 404 page |
| **Create** | `frontend/components.json` | shadcn/ui config |

---

## Task 1: Project Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/index.html`
- Create: `frontend/components.json`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "skavellion-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "@radix-ui/react-avatar": "^1.1.3",
    "@radix-ui/react-dialog": "^1.1.4",
    "@radix-ui/react-dropdown-menu": "^2.1.4",
    "@radix-ui/react-label": "^2.1.1",
    "@radix-ui/react-progress": "^1.1.0",
    "@radix-ui/react-separator": "^1.1.0",
    "@radix-ui/react-slot": "^1.1.1",
    "@radix-ui/react-tabs": "^1.1.2",
    "@radix-ui/react-toast": "^1.2.4",
    "@radix-ui/react-tooltip": "^1.1.6",
    "@tanstack/react-query": "^5.66.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.469.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.2",
    "tailwind-merge": "^2.6.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.5.1",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.7.2",
    "vite": "^6.0.11"
  }
}
```

- [ ] **Step 2: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
```

- [ ] **Step 3: Create tsconfig.json and tsconfig.app.json**

`frontend/tsconfig.json`:
```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" }
  ]
}
```

`frontend/tsconfig.app.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create index.html**

```html
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Skavellion</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create components.json (shadcn/ui config)**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/index.css",
    "baseColor": "slate",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide"
}
```

- [ ] **Step 6: Install dependencies**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm install`
Expected: `node_modules/` created, no errors

- [ ] **Step 7: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.app.json frontend/index.html frontend/components.json
git commit -m "feat: scaffold frontend project (Vite + React + TS)"
```

---

## Task 2: Tailwind & Design System

**Files:**
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/index.css`
- Create: `frontend/src/lib/utils.ts`

- [ ] **Step 1: Create tailwind.config.ts**

Design system from spec:
- Background: `#080d12`
- Sidebar/cards: `#0d1520`
- Accent: cyan `#06b6d4 → #0891b2`
- Text primary: `#e2e8f0`, secondary: `#94a3b8`, muted: `#475569`
- Borders: accent `rgba(6,182,212,0.15)`, neutral `rgba(255,255,255,0.07)`
- Radius: 14px cards, 10px inputs/buttons

```typescript
import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#080d12',
        surface: '#0d1520',
        accent: {
          DEFAULT: '#06b6d4',
          hover: '#0891b2',
        },
        text: {
          primary: '#e2e8f0',
          secondary: '#94a3b8',
          muted: '#475569',
        },
        border: {
          accent: 'rgba(6,182,212,0.15)',
          neutral: 'rgba(255,255,255,0.07)',
        },
      },
      borderRadius: {
        card: '14px',
        input: '10px',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

export default config
```

- [ ] **Step 2: Create postcss.config.js**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 3: Create src/index.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 210 50% 6%;
    --foreground: 214 32% 91%;
    --card: 214 42% 8%;
    --card-foreground: 214 32% 91%;
    --primary: 192 91% 44%;
    --primary-foreground: 0 0% 100%;
    --secondary: 214 16% 37%;
    --secondary-foreground: 214 32% 91%;
    --muted: 214 16% 37%;
    --muted-foreground: 215 16% 57%;
    --border: 214 32% 14%;
    --radius: 0.625rem;
  }

  * {
    border-color: rgba(255, 255, 255, 0.07);
  }

  body {
    @apply bg-background text-text-primary antialiased;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }

  ::-webkit-scrollbar {
    width: 6px;
  }
  ::-webkit-scrollbar-track {
    background: #080d12;
  }
  ::-webkit-scrollbar-thumb {
    background: #1e293b;
    border-radius: 3px;
  }
}
```

- [ ] **Step 4: Create src/lib/utils.ts**

```typescript
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 5: Verify Tailwind compiles**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run build 2>&1 | tail -5`
Expected: build succeeds (or type errors only — CSS compilation must work)

- [ ] **Step 6: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/tailwind.config.ts frontend/postcss.config.js frontend/src/index.css frontend/src/lib/utils.ts
git commit -m "feat: add Tailwind design system tokens"
```

---

## Task 3: API Types and Client

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create src/types/api.ts**

Mirror the backend response shapes:

```typescript
// src/types/api.ts

export interface ProviderInfo {
  type: string
  username: string | null
}

export interface UserProfile {
  id: string
  display_name: string
  is_admin: boolean
  created_at: string
  providers: ProviderInfo[]
}

export interface Subscription {
  type: 'trial' | 'paid'
  status: 'active' | 'expired' | 'disabled'
  started_at: string
  expires_at: string
  traffic_limit_gb: number | null
  synced_at: string | null
}

export interface Plan {
  id: string
  name: string
  label: string
  duration_days: number
  price_rub: number
  new_user_price_rub: number | null
  sort_order: number
}

export interface Article {
  id: string
  slug: string
  title: string
  preview_image_url: string | null
  sort_order: number
  created_at: string
}

export interface ArticleDetail extends Article {
  content: string
  updated_at: string
}

export interface Transaction {
  id: string
  type: 'trial_activation' | 'payment' | 'promo_bonus' | 'manual'
  status: 'pending' | 'completed' | 'failed'
  amount_rub: number | null
  days_added: number | null
  description: string | null
  created_at: string
  completed_at: string | null
}

export interface PaymentCreateResponse {
  payment_url: string
  transaction_id: string
}

export interface ValidatePromoResponse {
  code: string
  type: 'discount_percent' | 'bonus_days'
  value: number
  already_used: boolean
}

export interface ApplyPromoResponse {
  days_added: number
  new_expires_at: string
}

export interface InstallLinkResponse {
  subscription_url: string
}

export interface ApiError {
  detail: string
}
```

- [ ] **Step 2: Create src/lib/api.ts**

```typescript
// src/lib/api.ts

const BASE = ''  // same origin — Vite proxy handles /api in dev

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {}
    throw new ApiError(res.status, detail)
  }
  // 204 No Content
  if (res.status === 204) return undefined as unknown as T
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T = void>(path: string) => request<T>(path, { method: 'DELETE' }),
}
```

- [ ] **Step 3: Verify types compile**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run type-check 2>&1 | head -20`
Expected: no errors (or only "unused vars" type warnings if main.tsx not set up yet)

- [ ] **Step 4: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/src/types/api.ts frontend/src/lib/api.ts
git commit -m "feat: add API types and fetch client"
```

---

## Task 4: TanStack Query + Auth Hook

**Files:**
- Create: `frontend/src/lib/queryClient.ts`
- Create: `frontend/src/hooks/useAuth.ts`
- Create: `frontend/src/hooks/useSubscription.ts`

- [ ] **Step 1: Create src/lib/queryClient.ts**

```typescript
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error: unknown) => {
        // Don't retry on 401/403
        if (error instanceof Error && 'status' in error) {
          const status = (error as { status: number }).status
          if (status === 401 || status === 403) return false
        }
        return failureCount < 2
      },
    },
  },
})
```

- [ ] **Step 2: Create src/hooks/useAuth.ts**

```typescript
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { UserProfile } from '@/types/api'

export function useAuth() {
  const { data: user, isLoading, error } = useQuery<UserProfile>({
    queryKey: ['me'],
    queryFn: () => api.get<UserProfile>('/api/users/me'),
    retry: false,
    staleTime: 60_000,
  })

  return {
    user: user ?? null,
    isLoading,
    isAuthenticated: !!user,
    isAdmin: user?.is_admin ?? false,
    error,
  }
}
```

- [ ] **Step 3: Create src/hooks/useSubscription.ts**

```typescript
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Subscription } from '@/types/api'

export function useSubscription() {
  return useQuery<Subscription | null>({
    queryKey: ['subscription'],
    queryFn: async () => {
      try {
        return await api.get<Subscription>('/api/subscriptions/me')
      } catch (e: unknown) {
        if (e instanceof Error && 'status' in e && (e as { status: number }).status === 404) {
          return null
        }
        throw e
      }
    },
    staleTime: 30_000,
  })
}
```

- [ ] **Step 4: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/src/lib/queryClient.ts frontend/src/hooks/useAuth.ts frontend/src/hooks/useSubscription.ts
git commit -m "feat: add TanStack Query client and auth/subscription hooks"
```

---

## Task 5: App Entry + Router + Layout Shell

**Files:**
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/ProtectedRoute.tsx`
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/HomePage.tsx`
- Create: `frontend/src/pages/NotFoundPage.tsx`

- [ ] **Step 1: Create src/main.tsx**

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/queryClient'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
```

- [ ] **Step 2: Create src/App.tsx**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/Layout'
import ProtectedRoute from '@/components/ProtectedRoute'
import LoginPage from '@/pages/LoginPage'
import HomePage from '@/pages/HomePage'
import NotFoundPage from '@/pages/NotFoundPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 3: Create src/components/ProtectedRoute.tsx**

```tsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export default function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
```

- [ ] **Step 4: Create src/components/Layout.tsx**

Desktop sidebar (220px) + mobile bottom nav, as per spec. Nav items: Home `/`, Subscription `/subscription`, Install `/install`, Docs `/docs`, Support `/support`, Profile `/profile`.

```tsx
import { Outlet, NavLink } from 'react-router-dom'
import { Home, CreditCard, Download, BookOpen, MessageCircle, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'

const NAV_ITEMS = [
  { to: '/', label: 'Главная', icon: Home, exact: true },
  { to: '/subscription', label: 'Подписка', icon: CreditCard },
  { to: '/install', label: 'Установка', icon: Download },
  { to: '/docs', label: 'Документация', icon: BookOpen },
  { to: '/support', label: 'Поддержка', icon: MessageCircle },
  { to: '/profile', label: 'Профиль', icon: User },
]

function NavItem({ to, label, icon: Icon, exact }: typeof NAV_ITEMS[0]) {
  return (
    <NavLink
      to={to}
      end={exact}
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
      <span className="hidden md:block">{label}</span>
    </NavLink>
  )
}

export default function Layout() {
  const { user } = useAuth()

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-[220px] flex-col border-r border-border-neutral bg-surface px-4 py-6 shrink-0">
        {/* Logo */}
        <div className="mb-8 px-3">
          <span className="text-lg font-bold bg-gradient-to-r from-accent to-accent-hover bg-clip-text text-transparent">
            Skavellion
          </span>
        </div>
        {/* Nav */}
        <nav className="flex flex-col gap-1 flex-1">
          {NAV_ITEMS.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}
        </nav>
        {/* User badge */}
        {user && (
          <div className="mt-4 flex items-center gap-2 rounded-input px-3 py-2 bg-white/5">
            <div className="h-7 w-7 rounded-full bg-accent/20 flex items-center justify-center text-xs font-medium text-accent">
              {user.display_name[0].toUpperCase()}
            </div>
            <span className="text-xs text-text-secondary truncate">{user.display_name}</span>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto pb-20 md:pb-0">
        <Outlet />
      </main>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 border-t border-border-neutral bg-surface flex items-center justify-around px-2 py-2 z-50">
        {NAV_ITEMS.map(({ to, label, icon: Icon, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              cn(
                'flex flex-col items-center gap-0.5 px-2 py-1 rounded-input text-xs transition-colors',
                isActive ? 'text-accent' : 'text-text-muted',
              )
            }
          >
            <Icon size={20} />
            <span className="text-[10px]">{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
```

- [ ] **Step 5: Create page placeholders**

`frontend/src/pages/LoginPage.tsx`:
```tsx
export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-card bg-surface p-8 border border-border-neutral">
        <h1 className="text-xl font-bold text-text-primary mb-2">Вход в Skavellion</h1>
        <p className="text-sm text-text-secondary">Страница входа — в разработке</p>
      </div>
    </div>
  )
}
```

`frontend/src/pages/HomePage.tsx`:
```tsx
export default function HomePage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-text-primary">Главная</h1>
      <p className="mt-2 text-text-secondary">В разработке</p>
    </div>
  )
}
```

`frontend/src/pages/NotFoundPage.tsx`:
```tsx
import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center px-4">
      <h1 className="text-4xl font-bold text-text-primary">404</h1>
      <p className="text-text-secondary">Страница не найдена</p>
      <Link to="/" className="text-accent hover:underline text-sm">
        На главную
      </Link>
    </div>
  )
}
```

- [ ] **Step 6: Verify dev server starts**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run dev -- --port 3000 &`

Then check: `curl -s http://localhost:3000 | head -5`
Expected: HTML response with `<div id="root">`

Kill dev server after check.

- [ ] **Step 7: Build succeeds**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run build 2>&1 | tail -10`
Expected: build completed, `dist/` populated

- [ ] **Step 8: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages
git add frontend/src/
git commit -m "feat: add app shell — router, layout, auth hook, placeholder pages"
```

---

## Final Verification

- [ ] **Type check passes**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run type-check 2>&1 | head -20`
Expected: no errors

- [ ] **Build passes**

Run: `cd E:/Projects/vpn/custom_sub_pages/frontend && npm run build 2>&1 | tail -5`
Expected: `dist/` populated, no errors

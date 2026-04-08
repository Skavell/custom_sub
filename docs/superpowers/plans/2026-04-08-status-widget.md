# Status Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Uptime Kuma status widget to the bottom of the homepage that fetches live monitor data directly from the public API and shows each server/service status with a collapsible grouped list.

**Architecture:** A single new component `StatusWidget.tsx` fetches two Uptime Kuma API endpoints using `useQuery`, merges monitor names with live heartbeat data, and renders a collapsible banner + grouped list. The component is dropped into the existing `HomePage.tsx` with no backend changes.

**Tech Stack:** React 18, TypeScript, TanStack Query v5 (`@tanstack/react-query`), Tailwind CSS with project design tokens (`rounded-card`, `bg-surface`, `border-border-neutral`, `rounded-input`, `bg-white/5`, `text-text-muted`, `text-text-primary`, `text-text-secondary`, `text-accent`)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/components/StatusWidget.tsx` | **Create** | All widget logic and sub-components |
| `frontend/src/pages/HomePage.tsx` | **Modify** | Add `<StatusWidget />` after quick-links grid |

---

## Task 1: Create `StatusWidget.tsx` — types, constants, and `StatusRow`

**Files:**
- Create: `frontend/src/components/StatusWidget.tsx`

- [ ] **Step 1: Create the file with types, constants, and `StatusRow`**

Create `frontend/src/components/StatusWidget.tsx` with the following content:

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'

// The group whose monitors show ping instead of uptime
const PING_GROUP_NAME = 'Серверы'

const UPTIME_KUMA_BASE = 'https://status.example.com'
const STATUS_PAGE_SLUG = 'nodes'

// ── Types ────────────────────────────────────────────────────────────────────

interface Monitor {
  id: number
  name: string
  status: 0 | 1
  ping: number | null
  uptime: number | null // 0–100 percentage, null if unavailable
}

interface MonitorGroup {
  name: string
  monitors: Monitor[]
}

// Uptime Kuma API shapes (relevant fields only)
interface UptimeKumaNodes {
  publicGroupList: Array<{
    name: string
    monitorList: Array<{ id: number; name: string }>
  }>
}

interface UptimeKumaHeartbeat {
  heartbeatList: Record<string, Array<{ status: 0 | 1; ping: number | null }>>
  uptimeList: Record<string, number>
}

// ── StatusRow ─────────────────────────────────────────────────────────────────

interface StatusRowProps {
  name: string
  status: 0 | 1
  ping: number | null
  uptime: number | null
  showPing: boolean
}

function StatusRow({ name, status, ping, uptime, showPing }: StatusRowProps) {
  const isUp = status === 1

  let rightValue: string
  if (!isUp) {
    rightValue = 'недоступен'
  } else if (showPing) {
    rightValue = ping !== null ? `${ping}мс` : '—'
  } else {
    rightValue = uptime !== null ? `${uptime.toFixed(1)}%` : '—'
  }

  return (
    <div
      className={cn(
        'flex items-center justify-between rounded-input px-2.5 py-1.5',
        isUp
          ? 'bg-white/5'
          : 'bg-red-500/10 border border-red-500/20'
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span
          className={cn(
            'w-1.5 h-1.5 rounded-full shrink-0',
            isUp ? 'bg-emerald-500' : 'bg-red-500'
          )}
        />
        <span className="text-xs text-text-secondary truncate">{name}</span>
      </div>
      <span
        className={cn(
          'text-xs shrink-0 ml-2',
          isUp ? 'text-emerald-500' : 'text-red-400'
        )}
      >
        {rightValue}
      </span>
    </div>
  )
}
```

- [ ] **Step 2: Verify the file was created and TypeScript is clean**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors (the file is incomplete but exports nothing yet — if tsc complains about unused types that's fine; errors about missing imports are not).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/StatusWidget.tsx
git commit -m "feat: add StatusRow component scaffold"
```

---

## Task 2: Add `StatusGroup` and `StatusBanner` to `StatusWidget.tsx`

**Files:**
- Modify: `frontend/src/components/StatusWidget.tsx`

- [ ] **Step 1: Append `StatusGroup` after the `StatusRow` function**

Add after `StatusRow`:

```tsx
// ── StatusGroup ───────────────────────────────────────────────────────────────

interface StatusGroupProps {
  name: string
  monitors: Monitor[]
  showPing: boolean
}

function StatusGroup({ name, monitors, showPing }: StatusGroupProps) {
  return (
    <div className="mb-3 last:mb-0">
      <p className="text-xs uppercase tracking-wide text-text-muted mb-1.5 px-0.5">
        {name}
      </p>
      <div className="flex flex-col gap-1">
        {monitors.map((m) => (
          <StatusRow
            key={m.id}
            name={m.name}
            status={m.status}
            ping={m.ping}
            uptime={m.uptime}
            showPing={showPing}
          />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Append `StatusBanner` after `StatusGroup`**

Add after `StatusGroup`:

```tsx
// ── StatusBanner ──────────────────────────────────────────────────────────────

interface StatusBannerProps {
  isOpen: boolean
  onToggle: () => void
  upCount: number
  totalCount: number
  isLoading: boolean
  isError: boolean
}

function StatusBanner({
  isOpen,
  onToggle,
  upCount,
  totalCount,
  isLoading,
  isError,
}: StatusBannerProps) {
  const canExpand = !isLoading && !isError

  let dotColor: string
  let label: string

  if (isLoading) {
    dotColor = 'bg-slate-500'
    label = 'Загрузка...'
  } else if (isError) {
    dotColor = 'bg-slate-500'
    label = 'Статус недоступен'
  } else if (upCount === 0 && totalCount > 0) {
    dotColor = 'bg-red-500'
    label = 'Есть проблемы'
  } else if (upCount < totalCount) {
    dotColor = 'bg-emerald-500'
    label = 'Есть проблемы'
  } else {
    dotColor = 'bg-emerald-500'
    label = 'Все системы работают'
  }

  return (
    <button
      onClick={canExpand ? onToggle : undefined}
      disabled={!canExpand}
      className={cn(
        'w-full flex items-center justify-between rounded-input px-3 py-2.5 bg-white/5 border border-border-neutral transition-colors',
        canExpand && 'hover:border-accent/30 cursor-pointer'
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'w-2 h-2 rounded-full shrink-0',
            dotColor,
            !isLoading && !isError && 'animate-pulse'
          )}
        />
        <span className="text-sm text-text-primary font-medium">{label}</span>
      </div>
      {canExpand && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">
            {upCount}/{totalCount}
          </span>
          <span className="text-xs text-text-muted">
            {isOpen ? '▲' : '▼'}
          </span>
        </div>
      )}
    </button>
  )
}
```

- [ ] **Step 3: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/StatusWidget.tsx
git commit -m "feat: add StatusGroup and StatusBanner components"
```

---

## Task 3: Add `StatusWidget` main component with data fetching

**Files:**
- Modify: `frontend/src/components/StatusWidget.tsx`

- [ ] **Step 1: Append the main `StatusWidget` export after `StatusBanner`**

Add at the end of the file:

```tsx
// ── Data merge ────────────────────────────────────────────────────────────────

function mergeData(
  nodes: UptimeKumaNodes,
  heartbeat: UptimeKumaHeartbeat
): MonitorGroup[] {
  return nodes.publicGroupList
    .map((group) => {
      const monitors: Monitor[] = group.monitorList.map((m) => {
        const beats = heartbeat.heartbeatList[String(m.id)]
        const lastBeat = beats && beats.length > 0 ? beats[beats.length - 1] : null
        const uptimeRaw = heartbeat.uptimeList[`${m.id}_24`]
        return {
          id: m.id,
          name: m.name,
          status: lastBeat ? lastBeat.status : 0,
          ping: lastBeat ? lastBeat.ping : null,
          uptime: uptimeRaw !== undefined ? uptimeRaw * 100 : null,
        }
      })
      return { name: group.name, monitors }
    })
    .filter((g) => g.monitors.length > 0)
}

// ── StatusWidget (default export) ─────────────────────────────────────────────

export default function StatusWidget() {
  const [isOpen, setIsOpen] = useState(false)

  const { data: nodes } = useQuery<UptimeKumaNodes>({
    queryKey: ['statusNodes'],
    queryFn: () =>
      fetch(`${UPTIME_KUMA_BASE}/api/status-page/${STATUS_PAGE_SLUG}`).then(
        (r) => r.json()
      ),
    staleTime: 5 * 60 * 1000,
  })

  const {
    data: heartbeat,
    isLoading,
    isError,
  } = useQuery<UptimeKumaHeartbeat>({
    queryKey: ['statusHeartbeat'],
    queryFn: () =>
      fetch(
        `${UPTIME_KUMA_BASE}/api/status-page/heartbeat/${STATUS_PAGE_SLUG}`
      ).then((r) => r.json()),
    refetchInterval: 3 * 60 * 1000,
    staleTime: 3 * 60 * 1000,
  })

  const groups: MonitorGroup[] =
    nodes && heartbeat ? mergeData(nodes, heartbeat) : []

  const totalCount = groups.reduce((s, g) => s + g.monitors.length, 0)
  const upCount = groups.reduce(
    (s, g) => s + g.monitors.filter((m) => m.status === 1).length,
    0
  )

  return (
    <div className="rounded-card bg-surface border border-border-neutral p-4">
      <p className="text-xs text-text-muted uppercase tracking-wide mb-3">
        Статус серверов
      </p>

      <StatusBanner
        isOpen={isOpen}
        onToggle={() => setIsOpen((v) => !v)}
        upCount={upCount}
        totalCount={totalCount}
        isLoading={isLoading}
        isError={isError}
      />

      {isOpen && groups.length > 0 && (
        <div className="mt-3">
          {groups.map((g) => (
            <StatusGroup
              key={g.name}
              name={g.name}
              monitors={g.monitors}
              showPing={g.name === PING_GROUP_NAME}
            />
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Run TypeScript check — must pass clean**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/StatusWidget.tsx
git commit -m "feat: add StatusWidget with Uptime Kuma data fetching"
```

---

## Task 4: Integrate `StatusWidget` into `HomePage.tsx`

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: Add the import**

At the top of `frontend/src/pages/HomePage.tsx`, after the existing imports, add:

```tsx
import StatusWidget from '@/components/StatusWidget'
```

- [ ] **Step 2: Add `<StatusWidget />` after the quick-links grid**

In `HomePage.tsx`, find the quick-links grid block (it ends with `</div>` after the three Link items). Add the widget right after it:

```tsx
      {/* Status widget */}
      <div className="mt-6">
        <StatusWidget />
      </div>
```

The return block of `HomePage` should look like:

```tsx
  return (
    <div className="p-4 md:p-6 max-w-xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-5">Главная</h1>

      {showVerifyBanner && emailProvider?.identifier && (
        <EmailVerificationBanner userEmail={emailProvider.identifier} />
      )}

      {/* Subscription block */}
      {sub === null || sub === undefined ? (
        <TrialCTA ... />
      ) : sub.status === 'active' && sub.type === 'trial' ? (
        <TrialCard sub={sub} />
      ) : sub.status === 'active' && sub.type === 'paid' ? (
        <PaidCard sub={sub} />
      ) : (
        <ExpiredCard />
      )}

      {/* Quick links */}
      <div className="mt-6 grid grid-cols-3 gap-3">
        {[...].map(...)}
      </div>

      {/* Status widget */}
      <div className="mt-6">
        <StatusWidget />
      </div>
    </div>
  )
```

- [ ] **Step 3: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Start the dev server and visually verify**

```bash
cd frontend && npm run dev
```

Open the app in a browser and check:
1. Status widget appears at the bottom of the homepage
2. Banner shows "Загрузка..." briefly, then updates to "Все системы работают" (or correct status)
3. Clicking the banner expands the list showing two groups: "Серверы" and "Остальная инфраструктура"
4. Each server row shows a green dot and ping in `Xмс` format
5. Each infrastructure row shows a green dot and uptime `%`
6. Clicking again collapses the list
7. Open DevTools → Network: verify requests to `status.example.com` succeed (no CORS errors)

If CORS errors appear in the console, stop here and raise to the human — the backend proxy approach (Option B from the spec) will be needed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/HomePage.tsx
git commit -m "feat: integrate StatusWidget into homepage"
```

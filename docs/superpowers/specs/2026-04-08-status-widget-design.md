# Status Widget Design

**Date:** 2026-04-08  
**Status:** Approved

## Overview

Add an Uptime Kuma status widget to the bottom of the homepage (`HomePage.tsx`). The widget shows the real-time status of all monitored servers and infrastructure services fetched directly from the public Uptime Kuma API — no backend changes required.

## Data Sources

Two requests to the Uptime Kuma instance at `https://status.example.com`:

| Endpoint | Purpose | Cache / Refresh |
|---|---|---|
| `GET /api/status-page/nodes` | Monitor structure: group names, monitor names and IDs | `staleTime: 5 minutes` |
| `GET /api/status-page/heartbeat/nodes` | Live data: status (up/down), ping (ms), uptime (%) | `refetchInterval: 3 minutes` |

### API Response Shapes

**`/api/status-page/nodes`** returns (relevant fields only):
```ts
{
  publicGroupList: Array<{
    name: string          // e.g. "Серверы"
    monitorList: Array<{
      id: number
      name: string        // e.g. "🇳🇱 Нидерланды | 1"
    }>
  }>
}
```

**`/api/status-page/heartbeat/nodes`** returns:
```ts
{
  heartbeatList: {
    [monitorId: string]: Array<{
      status: 0 | 1       // 0 = down, 1 = up
      ping: number | null // latency in ms, null if not recorded
      time: string        // ISO timestamp
    }>
  },
  uptimeList: {
    [key: string]: number // key format: "<monitorId>_24" → 24h uptime as 0–1 float
  }
}
```

### Merge Logic

For each group in `publicGroupList`, for each monitor in `monitorList`:
1. Take the **last element** of `heartbeatList[monitor.id]` as the current heartbeat
2. Look up uptime via `uptimeList[`${monitor.id}_24`]` (multiply by 100 for percentage)
3. Produce a `Monitor` object: `{ id, name, status, ping, uptime }`

If `heartbeatList[monitor.id]` is undefined or empty, treat monitor as `status: 0, ping: null, uptime: null`. If `uptimeList["<id>_24"]` is missing independently, set `uptime: null`. Note: `heartbeatList` keys are strings, so access as `heartbeatList[String(monitor.id)]` to avoid TypeScript type errors.

Groups with an empty `monitors` array after merging are not rendered.

## Monitors (current)

**Group: Серверы**
- 🇳🇱 Нидерланды | 1
- 🇳🇱 Нидерланды | 2
- 🇳🇱 Нидерланды | 3

**Group: Остальная инфраструктура**
- Страница подписки
- Телеграм мини апп
- Телеграм бот

The widget dynamically renders all groups and monitors returned by the API — adding a new monitor in Uptime Kuma will automatically appear without code changes.

## Placement

Bottom of `HomePage.tsx`, after the quick-links grid (`mt-6` spacing consistent with the rest of the page).

## Components

Single file: `frontend/src/components/StatusWidget.tsx`

### Types

```ts
interface Monitor {
  id: number
  name: string
  status: 0 | 1
  ping: number | null
  uptime: number | null  // 0–100 percentage, null if unavailable
}

interface MonitorGroup {
  name: string
  monitors: Monitor[]
}
```

### `StatusWidget` (default export)
- Performs both `useQuery` calls
- Holds `isOpen: boolean` state (collapsed by default)
- Renders `StatusBanner` and, when open, a list of `StatusGroup`

### `StatusBanner`
```ts
Props: {
  isOpen: boolean
  onToggle: () => void
  upCount: number
  totalCount: number
  isLoading: boolean
  isError: boolean
}
```

- Pulsing dot color:
  - Grey, no pulse — loading or error
  - Green, pulsing — at least one monitor is up (intentionally green even when some are down — "Есть проблемы" label communicates partial degradation without alarming the user)
  - Red, pulsing — all monitors are down (`upCount === 0 && totalCount > 0`)
- Label:
  - "Загрузка..." — while loading
  - "Статус недоступен" — on error (no chevron, not expandable)
  - "Все системы работают" — `upCount === totalCount`
  - "Есть проблемы" — `upCount < totalCount` (including all-down)
- Counter `N/M` in muted grey — hidden during loading/error
- Chevron (▼/▲) — hidden during loading/error

### `StatusGroup`
```ts
Props: {
  name: string
  monitors: Monitor[]
  showPing: boolean
}
```

- Section label in small uppercase muted text
- List of `StatusRow`
- `showPing` is passed down from parent; determined by group name: `name === 'Серверы'`. This string is defined as a constant `PING_GROUP_NAME = 'Серверы'` at the top of the file, making it easy to update if the group is renamed in Uptime Kuma.

### `StatusRow`
```ts
Props: {
  name: string
  status: 0 | 1
  ping: number | null
  uptime: number | null
  showPing: boolean
}
```

- Green dot + green right-side value if `status === 1`
- Red dot + red "недоступен" text + red-tinted row background + subtle red border if `status === 0`
- Right-side value when `status === 1`:
  - If `showPing` is true: show `Xмс` if ping is not null, else `—`
  - If `showPing` is false: show `XX.X%` if uptime is not null, else `—`
- Right-side value when `status === 0`: always show "недоступен" regardless of showPing

## States

| State | Dot | Pulse | Label | Counter | Expandable |
|---|---|---|---|---|---|
| Loading | Grey | No | "Загрузка..." | hidden | No |
| Error | Grey | No | "Статус недоступен" | hidden | No |
| All up | Green | Yes | "Все системы работают" | grey | Yes |
| Some down | Green | Yes | "Есть проблемы" | grey | Yes |
| All down | Red | Yes | "Есть проблемы" | grey | Yes |

## Styling

Follows existing design tokens from the project:
- Container: `rounded-card bg-surface border border-border-neutral p-4`
- Group label: `text-xs uppercase tracking-wide text-text-muted`
- Monitor row: `rounded-input bg-white/5` (up), red-tinted background (down)
- Consistent with `StatusBadge` color conventions already used in `HomePage.tsx`

## Files Changed

| File | Change |
|---|---|
| `frontend/src/components/StatusWidget.tsx` | **New file** — full widget implementation |
| `frontend/src/pages/HomePage.tsx` | Add `<StatusWidget />` after quick-links grid |

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

Data from both responses is merged by monitor ID to produce a list of groups, each containing monitors with their name and live status.

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

### `StatusWidget` (default export)
- Performs both `useQuery` calls
- Holds `isOpen: boolean` state (collapsed by default)
- Renders `StatusBanner` and, when open, a list of `StatusGroup`

### `StatusBanner`
Props: `isOpen`, `onToggle`, `upCount`, `totalCount`, `isLoading`, `isError`

- Pulsing dot color:
  - Grey — loading or error
  - Green — at least one monitor is up (including "есть проблемы" state)
  - Red — all monitors are down
- Label:
  - "Загрузка..." — while loading
  - "Статус недоступен" — on error (no chevron, not expandable)
  - "Все системы работают" — all up
  - "Есть проблемы" — one or more down
- Counter `N/M` in muted grey — hidden during loading/error
- Chevron (▼/▲) — hidden during loading/error

### `StatusGroup`
Props: `name: string`, `monitors: Monitor[]`

- Section label in small uppercase muted text
- List of `StatusRow`

### `StatusRow`
Props: `name: string`, `status: 0 | 1`, `ping: number | null`, `uptime: number | null`, `showPing: boolean`

- Green dot + green right-side value if `status === 1`
- Red dot + red "недоступен" + red-tinted row background + subtle red border if `status === 0`
- Right-side value: ping in `Xмс` format if `showPing` is true, otherwise uptime as `XX.X%`
- `showPing` is true for the "Серверы" group, false for others

## States

| State | Dot | Label | Counter | Expandable |
|---|---|---|---|---|
| Loading | Grey (no pulse) | "Загрузка..." | hidden | No |
| Error | Grey | "Статус недоступен" | hidden | No |
| All up | Green (pulse) | "Все системы работают" | grey | Yes |
| Some down | Green (pulse) | "Есть проблемы" | grey | Yes |
| All down | Red (pulse) | "Есть проблемы" | grey | Yes |

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

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'

// The group whose monitors show ping instead of uptime
const PING_GROUP_NAME = 'Сервера'

const UPTIME_KUMA_BASE = import.meta.env.VITE_UPTIME_KUMA_BASE as string ?? ''
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
    nodes?.publicGroupList && heartbeat ? mergeData(nodes, heartbeat) : []

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

export { StatusRow, StatusGroup, StatusBanner }
export type { Monitor, MonitorGroup, StatusRowProps, StatusGroupProps, StatusBannerProps }

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

export { StatusRow }
export type { Monitor, MonitorGroup, StatusRowProps }

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
        if (s.status === 'completed' || s.status === 'failed' || s.status === 'timed_out') {
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
                : status.status === 'timed_out'
                ? 'Таймаут'
                : 'Выполняется...'}
            </span>
            {status.status === 'completed' && <CheckCircle size={16} className="text-green-400" />}
            {(status.status === 'failed' || status.status === 'timed_out') && <XCircle size={16} className="text-red-400" />}
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

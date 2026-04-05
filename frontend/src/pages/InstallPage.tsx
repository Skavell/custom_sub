import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Smartphone, Monitor, Terminal, Download, ExternalLink, Copy, Check, ChevronRight, ChevronLeft, AlertTriangle } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import type { InstallLinkResponse, InstallAppConfig } from '@/types/api'

type OS = 'android' | 'ios' | 'windows' | 'macos' | 'linux'

function detectOS(): OS {
  const ua = navigator.userAgent.toLowerCase()
  if (/android/.test(ua)) return 'android'
  if (/iphone|ipad|ipod/.test(ua)) return 'ios'
  if (/win/.test(ua)) return 'windows'
  if (/mac/.test(ua)) return 'macos'
  return 'linux'
}

const OS_TABS: { id: OS; label: string; icon: React.ComponentType<{ size?: string | number; className?: string }> }[] = [
  { id: 'android', label: 'Android', icon: Smartphone },
  { id: 'ios', label: 'iOS', icon: Smartphone },
  { id: 'windows', label: 'Windows', icon: Monitor },
  { id: 'macos', label: 'macOS', icon: Monitor },
  { id: 'linux', label: 'Linux', icon: Terminal },
]

const DEEP_LINK_TEMPLATES: Record<string, (sub: string, name: string) => string> = {
  flclash: (sub) => `flclash://install-config?url=${encodeURIComponent(sub)}`,
  clash_mi: (sub, name) =>
    `clash://install-config?overwrite=no&name=${encodeURIComponent(name)}&url=${encodeURIComponent(sub)}`,
  clash_meta: (sub, name) =>
    `clashmeta://install-config?name=${encodeURIComponent(name)}&url=${encodeURIComponent(sub)}`,
}

const OS_APP_KEY: Record<OS, string> = {
  android: 'flclash',
  ios: 'clash_mi',
  windows: 'flclash',
  macos: 'flclash',
  linux: 'flclash',
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
      className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors shrink-0"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? 'Скопировано' : 'Скопировать'}
    </button>
  )
}

export default function InstallPage() {
  const { user } = useAuth()
  const [activeOS, setActiveOS] = useState<OS>(detectOS)
  const [step, setStep] = useState<1 | 2>(1)

  const { data: installData, isLoading, error } = useQuery<InstallLinkResponse>({
    queryKey: ['subscriptionLink'],
    queryFn: () => api.get<InstallLinkResponse>('/api/install/subscription-link'),
    retry: false,
    staleTime: 60_000,
  })

  const { data: appConfig } = useQuery<InstallAppConfig>({
    queryKey: ['installAppConfig'],
    queryFn: () => api.get<InstallAppConfig>('/api/install/app-config'),
    staleTime: 10 * 60_000,
  })

  const is403 = error instanceof ApiError && error.status === 403
  const subLink = installData?.subscription_url ?? ''
  const displayName = user?.display_name ?? 'VPN'

  const osConfig = appConfig?.[activeOS]
  const appName = osConfig?.app_name ?? '…'
  const storeUrl = osConfig?.store_url ?? '#'
  const deepLinkFn = DEEP_LINK_TEMPLATES[OS_APP_KEY[activeOS]]
  const deepLink = subLink && deepLinkFn ? deepLinkFn(subLink, displayName) : null

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
        <div className="flex items-center gap-2 mb-5 text-sm text-text-muted">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          Загрузка ссылки…
        </div>
      )}

      {/* OS tabs */}
      <div className="flex gap-1 bg-surface border border-border-neutral rounded-card p-1 mb-5 overflow-x-auto">
        {OS_TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => { setActiveOS(id); setStep(1) }}
            className={cn(
              'flex items-center gap-1.5 rounded-input px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors',
              activeOS === id ? 'bg-accent/15 text-accent' : 'text-text-muted hover:text-text-secondary',
            )}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-3 mb-5">
        <div className="flex items-center gap-2">
          <div className={cn(
            'h-6 w-6 rounded-full text-xs font-bold flex items-center justify-center',
            step === 1 ? 'bg-accent text-white' : 'bg-accent/20 text-accent',
          )}>1</div>
          <span className={cn('text-xs font-medium', step === 1 ? 'text-text-primary' : 'text-text-muted')}>
            Установка приложения
          </span>
        </div>
        <div className="flex-1 h-px bg-border-neutral" />
        <div className="flex items-center gap-2">
          <div className={cn(
            'h-6 w-6 rounded-full text-xs font-bold flex items-center justify-center',
            step === 2 ? 'bg-accent text-white' : 'bg-white/10 text-text-muted',
          )}>2</div>
          <span className={cn('text-xs font-medium', step === 2 ? 'text-text-primary' : 'text-text-muted')}>
            Добавление подписки
          </span>
        </div>
      </div>

      {/* Step 1 */}
      {step === 1 && (
        <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
          <h2 className="text-base font-semibold text-text-primary mb-1">Скачайте {appName}</h2>
          <p className="text-sm text-text-muted mb-5">
            Установите приложение на ваше устройство
          </p>

          <a
            href={storeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 w-full text-center rounded-input bg-accent hover:bg-accent-hover text-white font-medium py-3 text-sm transition-colors mb-4"
          >
            <Download size={14} />
            Скачать {appName}
          </a>

          <div className="flex items-start gap-2.5 rounded-input bg-yellow-500/10 border border-yellow-500/20 px-3 py-2.5 mb-5">
            <AlertTriangle size={14} className="text-yellow-400 shrink-0 mt-0.5" />
            <p className="text-xs text-yellow-300">
              После установки обязательно вернитесь на эту страницу для добавления подписки
            </p>
          </div>

          <button
            onClick={() => setStep(2)}
            className="flex items-center justify-center gap-2 w-full rounded-input border border-border-neutral bg-white/5 hover:bg-white/10 text-text-secondary font-medium py-2.5 text-sm transition-colors"
          >
            Приложение установлено, далее
            <ChevronRight size={14} />
          </button>
        </div>
      )}

      {/* Step 2 */}
      {step === 2 && (
        <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
          <h2 className="text-base font-semibold text-text-primary mb-1">Добавьте подписку</h2>
          <p className="text-sm text-text-muted mb-5">
            Нажмите кнопку ниже — подписка добавится в {appName} автоматически
          </p>

          {deepLink ? (
            <a
              href={deepLink}
              className="flex items-center justify-center gap-2 w-full text-center rounded-input bg-accent hover:bg-accent-hover text-white font-medium py-3 text-sm transition-colors mb-4"
            >
              <ExternalLink size={14} />
              Добавить подписку в {appName}
            </a>
          ) : (
            <div className="rounded-input bg-white/5 border border-border-neutral px-4 py-3 text-xs text-text-muted mb-4">
              {isLoading ? 'Загрузка ссылки…' : 'Подписка недоступна'}
            </div>
          )}

          {subLink && (
            <div className="rounded-card bg-white/5 border border-border-neutral p-4 mb-4">
              <p className="text-xs text-text-muted mb-2">
                Если кнопка не сработала — добавьте ссылку вручную:
              </p>
              <div className="flex items-center gap-2 bg-background rounded-input p-3">
                <code className="flex-1 text-xs text-text-secondary break-all">{subLink}</code>
                <CopyButton text={subLink} />
              </div>
            </div>
          )}

          <button
            onClick={() => setStep(1)}
            className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-secondary transition-colors"
          >
            <ChevronLeft size={13} />
            Назад
          </button>
        </div>
      )}
    </div>
  )
}

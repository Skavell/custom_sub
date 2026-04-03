import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Smartphone, Monitor, Download, Terminal, ExternalLink, Copy, Check } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import type { InstallLinkResponse } from '@/types/api'

type OS = 'android' | 'ios' | 'windows' | 'macos' | 'linux'

function detectOS(): OS {
  const ua = navigator.userAgent.toLowerCase()
  if (/android/.test(ua)) return 'android'
  if (/iphone|ipad|ipod/.test(ua)) return 'ios'
  if (/win/.test(ua)) return 'windows'
  if (/mac/.test(ua)) return 'macos'
  return 'linux'
}

const OS_TABS: { id: OS; label: string; icon: React.ComponentType<{ size?: number; className?: string }> }[] = [
  { id: 'android', label: 'Android', icon: Smartphone },
  { id: 'ios', label: 'iOS', icon: Smartphone },
  { id: 'windows', label: 'Windows', icon: Monitor },
  { id: 'macos', label: 'macOS', icon: Monitor },
  { id: 'linux', label: 'Linux', icon: Terminal },
]

interface AppInfo {
  name: string
  deepLinkTemplate: (sub: string, name: string) => string
  storeUrl: string
  steps: string[]
}

const APPS: Record<string, AppInfo> = {
  flclash: {
    name: 'FlClash',
    deepLinkTemplate: (sub) => `flclash://install-config?url=${encodeURIComponent(sub)}`,
    storeUrl: 'https://github.com/chen08209/FlClash/releases/latest',
    steps: [
      'Установите FlClash',
      'Нажмите кнопку ниже для автоматической настройки',
      'Разрешите добавление профиля в приложении',
      'Включите туннель',
    ],
  },
  clash_mi: {
    name: 'Clash Mi',
    deepLinkTemplate: (sub, name) =>
      `clash://install-config?overwrite=no&name=${encodeURIComponent(name)}&url=${encodeURIComponent(sub)}`,
    storeUrl: 'https://apps.apple.com/app/clash-mi/id1574653991',
    steps: [
      'Установите Clash Mi из App Store',
      'Нажмите кнопку ниже для автоматической настройки',
      'Подтвердите добавление VPN-профиля',
      'Включите туннель',
    ],
  },
  clash_meta: {
    name: 'Clash Meta',
    deepLinkTemplate: (sub, name) =>
      `clashmeta://install-config?name=${encodeURIComponent(name)}&url=${encodeURIComponent(sub)}`,
    storeUrl: 'https://github.com/MetaCubeX/ClashMetaForAndroid/releases/latest',
    steps: [
      'Установите Clash Meta',
      'Нажмите кнопку ниже для автоматической настройки',
      'Разрешите добавление профиля',
      'Включите туннель',
    ],
  },
  clash_verge: {
    name: 'Clash Verge Rev',
    deepLinkTemplate: (sub) => `clash://install-config?url=${encodeURIComponent(sub)}`,
    storeUrl: 'https://github.com/clash-verge-rev/clash-verge-rev/releases/latest',
    steps: [
      'Установите Clash Verge Rev',
      'Нажмите кнопку ниже для автоматической настройки',
      'Подтвердите импорт профиля',
      'Включите системный прокси',
    ],
  },
}

const OS_APPS: Record<OS, string[]> = {
  android: ['flclash', 'clash_meta'],
  ios: ['clash_mi'],
  windows: ['clash_verge', 'flclash'],
  macos: ['flclash', 'clash_verge'],
  linux: ['clash_verge'],
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
  const [activeApp, setActiveApp] = useState<string | null>(null)

  const { data: installData, isLoading, error } = useQuery<InstallLinkResponse>({
    queryKey: ['subscriptionLink'],
    queryFn: () => api.get<InstallLinkResponse>('/api/install/subscription-link'),
    retry: false,
    staleTime: 60_000,
  })

  const is403 = error instanceof ApiError && error.status === 403
  const appsForOS = OS_APPS[activeOS]
  const currentAppKey = activeApp ?? appsForOS[0]
  const app = APPS[currentAppKey]
  const subLink = installData?.subscription_url ?? ''
  const displayName = user?.display_name ?? 'Skavellion'

  function handleOSChange(os: OS) {
    setActiveOS(os)
    setActiveApp(null)
  }

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
            onClick={() => handleOSChange(id)}
            className={cn(
              'flex items-center gap-1.5 rounded-input px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors',
              activeOS === id
                ? 'bg-accent/15 text-accent'
                : 'text-text-muted hover:text-text-secondary',
            )}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </div>

      {/* App selector */}
      {appsForOS.length > 1 && (
        <div className="flex gap-2 mb-5">
          {appsForOS.map((key) => (
            <button
              key={key}
              onClick={() => setActiveApp(key)}
              className={cn(
                'rounded-input border px-3 py-1.5 text-xs font-medium transition-colors',
                currentAppKey === key
                  ? 'border-accent text-accent bg-accent/10'
                  : 'border-border-neutral text-text-secondary hover:border-accent/40',
              )}
            >
              {APPS[key].name}
            </button>
          ))}
        </div>
      )}

      {/* Install steps */}
      <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
        <h2 className="text-base font-semibold text-text-primary mb-4">{app.name}</h2>
        <ol className="space-y-4">
          {app.steps.map((step, i) => (
            <li key={i} className="flex gap-3">
              <span className="h-6 w-6 rounded-full bg-accent/15 text-accent text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                {i + 1}
              </span>
              <span className="text-sm text-text-secondary">{step}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Deep link button */}
      {subLink && (
        <a
          href={app.deepLinkTemplate(subLink, displayName)}
          className="flex items-center justify-center gap-2 w-full text-center rounded-input bg-accent hover:bg-accent-hover text-white font-medium py-3 text-sm transition-colors mb-4"
        >
          <ExternalLink size={14} />
          Открыть в {app.name}
        </a>
      )}

      {/* Manual fallback */}
      {subLink && (
        <div className="rounded-card bg-surface border border-border-neutral p-4">
          <p className="text-xs text-text-muted mb-2">Или вставьте ссылку вручную:</p>
          <div className="flex items-center gap-2 bg-white/5 rounded-input p-3">
            <code className="flex-1 text-xs text-text-secondary break-all">{subLink}</code>
            <CopyButton text={subLink} />
          </div>
        </div>
      )}

      {/* Download link for app */}
      {!subLink && !isLoading && !is403 && (
        <div className="rounded-card bg-surface border border-border-neutral p-4">
          <p className="text-xs text-text-muted mb-2">Скачать {app.name}:</p>
          <a
            href={app.storeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-accent hover:underline"
          >
            <Download size={14} />
            {app.storeUrl}
          </a>
        </div>
      )}
    </div>
  )
}

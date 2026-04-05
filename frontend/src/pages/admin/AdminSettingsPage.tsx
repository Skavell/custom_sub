// frontend/src/pages/admin/AdminSettingsPage.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Eye, EyeOff, ChevronDown, ChevronRight, ToggleLeft, ToggleRight } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { SettingAdminItem } from '@/types/api'

// Keys managed in the dedicated OAuth section (hidden from generic list)
const OAUTH_KEYS = new Set([
  'google_enabled', 'google_client_id', 'google_client_secret',
  'vk_enabled', 'vk_client_id', 'vk_client_secret',
  'email_enabled',
  'telegram_bot_token', 'telegram_bot_username',
  'support_telegram_link', 'telegram_support_chat_id',
])

// Keys that belong to the install apps group
const INSTALL_KEY_PREFIX = 'install_'

// ─── Generic setting row ─────────────────────────────────────────────────────

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
          <span className="text-xs bg-yellow-500/10 text-yellow-400 px-1.5 py-0.5 rounded">скрытое</span>
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
            saved ? 'bg-green-500/20 text-green-400' : 'bg-accent/10 text-accent hover:bg-accent/20'
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

// ─── OAuth provider field (single text input) ─────────────────────────────────

function OAuthField({
  label, settingKey, sensitive, placeholder, settings,
}: {
  label: string
  settingKey: string
  sensitive?: boolean
  placeholder?: string
  settings: SettingAdminItem[]
}) {
  const queryClient = useQueryClient()
  const existing = settings.find((s) => s.key === settingKey)
  const [value, setValue] = useState(existing?.value ?? '')
  const [showValue, setShowValue] = useState(false)
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${settingKey}`, { value: v, is_sensitive: sensitive ?? false }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setSaved(true)
      setErr(null)
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (e) => setErr(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  return (
    <div>
      <label className="block text-xs text-text-muted mb-1">{label}</label>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type={sensitive && !showValue ? 'password' : 'text'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder ?? (sensitive ? '••••••••' : 'Значение')}
            className="w-full rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
          {sensitive && (
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
            saved ? 'bg-green-500/20 text-green-400' : 'bg-accent/10 text-accent hover:bg-accent/20'
          } disabled:opacity-50`}
        >
          <Save size={13} />
          {saved ? 'Сохранено' : 'Сохранить'}
        </button>
      </div>
      {err && <p className="mt-1 text-xs text-red-400">{err}</p>}
    </div>
  )
}

// ─── Enable/disable toggle ────────────────────────────────────────────────────

function OAuthToggle({ label, settingKey, settings }: { label: string; settingKey: string; settings: SettingAdminItem[] }) {
  const queryClient = useQueryClient()
  const existing = settings.find((s) => s.key === settingKey)
  const enabled = existing?.value !== 'false'

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${settingKey}`, { value: v, is_sensitive: false }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-settings'] }),
  })

  return (
    <button
      onClick={() => mutation.mutate(enabled ? 'false' : 'true')}
      disabled={mutation.isPending}
      className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
    >
      {enabled
        ? <ToggleRight size={20} className="text-accent" />
        : <ToggleLeft size={20} className="text-text-muted" />
      }
      {label}
    </button>
  )
}

// ─── OAuth provider block ─────────────────────────────────────────────────────

function OAuthProviderBlock({
  title, enableKey, fields, settings,
}: {
  title: string
  enableKey: string
  fields: { label: string; key: string; sensitive?: boolean; placeholder?: string }[]
  settings: SettingAdminItem[]
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="rounded-input border border-border-neutral overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-white/3">
        <OAuthToggle label={title} settingKey={enableKey} settings={settings} />
        <button onClick={() => setOpen((v) => !v)} className="text-text-muted hover:text-text-primary transition-colors">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      </div>
      {open && (
        <div className="px-4 py-3 border-t border-border-neutral space-y-3">
          {fields.map((f) => (
            <OAuthField
              key={f.key}
              label={f.label}
              settingKey={f.key}
              sensitive={f.sensitive}
              placeholder={f.placeholder}
              settings={settings}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Collapsible group ────────────────────────────────────────────────────────

function CollapsibleGroup({ title, items }: { title: string; items: SettingAdminItem[] }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="rounded-input border border-border-neutral overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left bg-white/3 hover:bg-white/5 transition-colors"
      >
        <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">{title}</span>
        {open ? <ChevronDown size={14} className="text-text-muted" /> : <ChevronRight size={14} className="text-text-muted" />}
      </button>
      {open && (
        <div className="border-t border-border-neutral p-3 flex flex-col gap-2">
          {items.map((s) => <SettingRow key={s.key} setting={s} />)}
        </div>
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AdminSettingsPage() {
  const { data: settings, isLoading, error } = useQuery<SettingAdminItem[]>({
    queryKey: ['admin-settings'],
    queryFn: () => api.get<SettingAdminItem[]>('/api/admin/settings'),
    staleTime: 60_000,
  })

  const allSettings = settings ?? []

  // Separate settings into groups
  const installSettings = allSettings.filter(
    (s) => s.key.startsWith(INSTALL_KEY_PREFIX) && !OAUTH_KEYS.has(s.key),
  )
  const otherSettings = allSettings.filter(
    (s) => !s.key.startsWith(INSTALL_KEY_PREFIX) && !OAUTH_KEYS.has(s.key),
  )
  const regular = otherSettings.filter((s) => !s.is_sensitive)
  const sensitive = otherSettings.filter((s) => s.is_sensitive)

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

      {/* OAuth провайдеры */}
      {settings && (
        <div className="mb-6">
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2 px-1">
            OAuth провайдеры
          </h2>
          <div className="flex flex-col gap-2">
            <OAuthProviderBlock
              title="Google"
              enableKey="google_enabled"
              settings={allSettings}
              fields={[
                { label: 'Client ID', key: 'google_client_id', placeholder: 'xxx.apps.googleusercontent.com' },
                { label: 'Client Secret', key: 'google_client_secret', sensitive: true },
              ]}
            />
            <OAuthProviderBlock
              title="ВКонтакте"
              enableKey="vk_enabled"
              settings={allSettings}
              fields={[
                { label: 'Client ID', key: 'vk_client_id', placeholder: '12345678' },
                { label: 'Client Secret', key: 'vk_client_secret', sensitive: true },
              ]}
            />
            <OAuthProviderBlock
              title="Telegram"
              enableKey="telegram_bot_token"
              settings={allSettings}
              fields={[
                { label: 'Bot Token', key: 'telegram_bot_token', sensitive: true, placeholder: '123456:ABC…' },
                { label: 'Bot Username (без @)', key: 'telegram_bot_username', placeholder: 'mybot' },
                { label: 'Chat ID поддержки', key: 'telegram_support_chat_id', placeholder: '-100123456789' },
                { label: 'Ссылка поддержки', key: 'support_telegram_link', placeholder: 'https://t.me/…' },
              ]}
            />
            <div className={cn(
              'rounded-input border border-border-neutral px-4 py-3 flex items-center gap-2',
            )}>
              <OAuthToggle label="Email / Пароль" settingKey="email_enabled" settings={allSettings} />
            </div>
          </div>
        </div>
      )}

      {/* Приложения и ссылки (install_* keys) */}
      {installSettings.length > 0 && (
        <div className="mb-6">
          <CollapsibleGroup title="Приложения и ссылки" items={installSettings} />
        </div>
      )}

      {/* Основные */}
      {regular.length > 0 && (
        <div className="mb-5">
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2 px-1">Основные</h2>
          <div className="flex flex-col gap-2">
            {regular.map((s) => <SettingRow key={s.key} setting={s} />)}
          </div>
        </div>
      )}

      {/* Секреты */}
      {sensitive.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2 px-1">Секреты / токены</h2>
          <div className="flex flex-col gap-2">
            {sensitive.map((s) => <SettingRow key={s.key} setting={s} />)}
          </div>
        </div>
      )}
    </div>
  )
}

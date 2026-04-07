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

const INSTALL_KEY_PREFIX = 'install_'

const REMNAWAVE_KEYS = new Set([
  'remnawave_url', 'remnawave_token',
  'remnawave_trial_internal_squad_uuids', 'remnawave_trial_external_squad_uuids',
  'remnawave_paid_internal_squad_uuids', 'remnawave_paid_external_squad_uuids',
])

const TRIAL_KEYS = new Set([
  'remnawave_trial_days', 'remnawave_trial_traffic_limit_bytes',
])

const EMAIL_SERVICE_KEYS = new Set([
  'resend_api_key', 'email_from_address', 'email_from_name',
])

const REGISTRATION_KEYS = new Set([
  'registration_enabled', 'email_verification_enabled', 'allowed_email_domains',
])

const PAYMENT_KEYS = new Set([
  'cryptobot_enabled',
  'cryptobot_token',
  'usdt_exchange_rate',
  'cryptobot_webhook_allowed_ips',
])

const SETTING_LABELS: Record<string, string> = {
  remnawave_url: 'URL сервера Remnawave',
  remnawave_token: 'API токен Remnawave',
  remnawave_trial_internal_squad_uuids: 'Внутренние сквады (триал)',
  remnawave_trial_external_squad_uuids: 'Внешние сквады (триал)',
  remnawave_paid_internal_squad_uuids: 'Внутренние сквады (платная)',
  remnawave_paid_external_squad_uuids: 'Внешние сквады (платная)',
  remnawave_trial_days: 'Длительность триала (дней)',
  remnawave_trial_traffic_limit_bytes: 'Лимит трафика триала',
  resend_api_key: 'API ключ Resend',
  email_from_address: 'Адрес отправителя',
  email_from_name: 'Имя отправителя',
  registration_enabled: 'Регистрация открыта',
  email_verification_enabled: 'Подтверждение email обязательно',
  allowed_email_domains: 'Разрешённые домены',
}

const SETTING_HINTS: Record<string, string> = {
  remnawave_trial_internal_squad_uuids: 'UUID через запятую. Ноды вашей собственной инфраструктуры.',
  remnawave_trial_external_squad_uuids: 'UUID через запятую. Ноды внешних провайдеров.',
  remnawave_paid_internal_squad_uuids: 'UUID через запятую. Ноды вашей собственной инфраструктуры. Назначаются при оплате.',
  remnawave_paid_external_squad_uuids: 'UUID через запятую. Ноды внешних провайдеров. Назначаются при оплате.',
}

// ─── Generic setting row ─────────────────────────────────────────────────────

function SettingRow({
  setting,
  labelOverride,
  hint,
}: {
  setting: SettingAdminItem
  labelOverride?: string
  hint?: string
}) {
  const queryClient = useQueryClient()
  const [value, setValue] = useState(setting.value ?? '')
  const [showValue, setShowValue] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v, is_sensitive: setting.is_sensitive }),
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
      {(labelOverride || hint) && (
        <div className="mb-2">
          {labelOverride && <p className="text-sm text-text-primary">{labelOverride}</p>}
          {hint && <p className="text-xs text-text-muted mt-0.5">{hint}</p>}
        </div>
      )}
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

// ─── Toggle setting row ───────────────────────────────────────────────────────

function ToggleSettingRow({ setting, label, hint }: { setting: SettingAdminItem; label: string; hint?: string }) {
  const queryClient = useQueryClient()
  const [isOn, setIsOn] = useState(setting.value === 'true')
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v, is_sensitive: setting.is_sensitive }),
    onSuccess: (_, v) => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setIsOn(v === 'true')
      setSaveError(null)
    },
    onError: (e) => {
      setIsOn(setting.value === 'true')
      setSaveError(e instanceof ApiError ? e.detail : 'Ошибка')
    },
  })

  const toggle = () => {
    const newVal = isOn ? 'false' : 'true'
    setIsOn(!isOn)
    mutation.mutate(newVal)
  }

  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-text-primary">{label}</p>
          {hint && <p className="text-xs text-text-muted mt-0.5">{hint}</p>}
        </div>
        <button
          onClick={toggle}
          disabled={mutation.isPending}
          className={`relative w-10 h-5 rounded-full transition-colors ${isOn ? 'bg-accent' : 'bg-surface border border-border-neutral'}`}
        >
          <span
            className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${isOn ? 'translate-x-5' : ''}`}
          />
        </button>
      </div>
      {saveError && <p className="mt-1 text-xs text-red-400">{saveError}</p>}
    </div>
  )
}

// ─── Textarea setting row (for domain lists etc.) ─────────────────────────────

function TextareaSettingRow({ setting, label, hint }: { setting: SettingAdminItem; label: string; hint?: string }) {
  const queryClient = useQueryClient()
  const [value, setValue] = useState(
    (setting.value ?? '').split(',').map(d => d.trim()).filter(Boolean).join('\n')
  )
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v, is_sensitive: setting.is_sensitive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setSaved(true)
      setSaveError(null)
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  const handleSave = () => {
    const normalized = value
      .split('\n')
      .map(d => d.trim().toLowerCase())
      .filter(Boolean)
      .join(',')
    mutation.mutate(normalized)
  }

  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3 space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-text-primary">{label}</p>
          {hint && <p className="text-xs text-text-muted mt-0.5">{hint}</p>}
        </div>
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-input text-xs font-medium transition-colors ${
            saved ? 'bg-green-500/20 text-green-400' : 'bg-accent/10 text-accent hover:bg-accent/20'
          } disabled:opacity-50`}
        >
          <Save size={13} />
          {saved ? 'Сохранено' : 'Сохранить'}
        </button>
      </div>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={6}
        placeholder={"gmail.com\nmail.ru\nyandex.ru"}
        className="w-full rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent font-mono resize-none"
      />
      {saveError && <p className="text-xs text-red-400">{saveError}</p>}
    </div>
  )
}

// ─── Webhook IPs setting row ──────────────────────────────────────────────────

function WebhookIPsSettingRow({ setting, label, hint }: { setting: SettingAdminItem; label: string; hint?: string }) {
  const queryClient = useQueryClient()

  const loadIPs = (raw: string | null): string => {
    if (!raw || raw.trim() === '') return ''
    try { return (JSON.parse(raw) as string[]).join('\n') }
    catch { return raw }
  }

  const [value, setValue] = useState(() => loadIPs(setting.value ?? null))
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v, is_sensitive: setting.is_sensitive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setSaved(true)
      setSaveError(null)
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  const handleSave = () => {
    const ips = JSON.stringify(value.split('\n').map(s => s.trim()).filter(Boolean))
    mutation.mutate(ips)
  }

  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3 space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-text-primary">{label}</p>
          {hint && <p className="text-xs text-text-muted mt-0.5">{hint}</p>}
        </div>
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-input text-xs font-medium transition-colors ${
            saved ? 'bg-green-500/20 text-green-400' : 'bg-accent/10 text-accent hover:bg-accent/20'
          } disabled:opacity-50`}
        >
          <Save size={13} />
          {saved ? 'Сохранено' : 'Сохранить'}
        </button>
      </div>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={4}
        placeholder={"1.2.3.4\n5.6.7.8"}
        className="w-full rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent font-mono resize-none"
      />
      {saveError && <p className="text-xs text-red-400">{saveError}</p>}
    </div>
  )
}

// ─── Number (bytes) setting row ───────────────────────────────────────────────

function NumberBytesSettingRow({ setting, label, hint }: { setting: SettingAdminItem; label: string; hint?: string }) {
  const queryClient = useQueryClient()
  const GB = 1024 ** 3
  const [value, setValue] = useState(
    setting.value ? String(Math.round(parseInt(setting.value, 10) / GB)) : ''
  )
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v, is_sensitive: setting.is_sensitive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setSaved(true)
      setSaveError(null)
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  const handleSave = () => {
    const gb = parseInt(value, 10)
    if (isNaN(gb) || gb <= 0) { setSaveError('Введите корректное число ГБ'); return }
    mutation.mutate(String(gb * GB))
  }

  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="text-sm text-text-primary">{label}</p>
          {hint && <p className="text-xs text-text-muted mt-0.5">{hint}</p>}
        </div>
      </div>
      <div className="flex gap-2 items-center">
        <input
          type="number"
          min={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-28 rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
        />
        <span className="text-sm text-text-secondary">ГБ</span>
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className={`ml-auto flex items-center gap-1 px-3 py-1.5 rounded-input text-xs font-medium transition-colors ${
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
  label, settingKey, sensitive, placeholder, hint, settings,
}: {
  label: string
  settingKey: string
  sensitive?: boolean
  placeholder?: string
  hint?: string
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
      {hint && <p className="text-xs text-text-muted mb-1">{hint}</p>}
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

// ─── Collapsible section ──────────────────────────────────────────────────────

function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="rounded-card border border-border-neutral overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white/3 hover:bg-white/5 transition-colors"
      >
        <span className="text-sm font-medium text-text-primary">{title}</span>
        {open ? <ChevronDown size={14} className="text-text-muted" /> : <ChevronRight size={14} className="text-text-muted" />}
      </button>
      {open && (
        <div className="px-4 py-4 border-t border-border-neutral space-y-2">
          {children}
        </div>
      )}
    </div>
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

// ─── CryptoBot enabled toggle (inline) ───────────────────────────────────────

function CryptoBotEnabledToggle({ setting }: { setting: SettingAdminItem }) {
  const queryClient = useQueryClient()
  const [isOn, setIsOn] = useState(setting.value === 'true')

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v, is_sensitive: false }),
    onSuccess: (_, v) => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setIsOn(v === 'true')
    },
    onError: () => setIsOn(setting.value === 'true'),
  })

  const toggle = () => {
    const newVal = isOn ? 'false' : 'true'
    setIsOn(!isOn)
    mutation.mutate(newVal)
  }

  return (
    <button
      onClick={toggle}
      disabled={mutation.isPending}
      className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
    >
      {isOn
        ? <ToggleRight size={20} className="text-accent" />
        : <ToggleLeft size={20} className="text-text-muted" />
      }
      CryptoBot
    </button>
  )
}

// ─── CryptoBot block ──────────────────────────────────────────────────────────

function CryptoBotBlock({ settings }: { settings: SettingAdminItem[] }) {
  const [open, setOpen] = useState(false)

  const enabledSetting = settings.find(s => s.key === 'cryptobot_enabled')
  const tokenSetting = settings.find(s => s.key === 'cryptobot_token')
  const rateSetting = settings.find(s => s.key === 'usdt_exchange_rate')
  const webhookSetting = settings.find(s => s.key === 'cryptobot_webhook_allowed_ips')

  return (
    <div className="rounded-input border border-border-neutral overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-white/3">
        {enabledSetting ? (
          <CryptoBotEnabledToggle setting={enabledSetting} />
        ) : (
          <span className="text-sm text-text-secondary">CryptoBot</span>
        )}
        <button onClick={() => setOpen((v) => !v)} className="text-text-muted hover:text-text-primary transition-colors">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      </div>
      {open && (
        <div className="px-4 py-3 border-t border-border-neutral space-y-3">
          {tokenSetting && (
            <OAuthField
              label="API токен CryptoBot"
              settingKey="cryptobot_token"
              sensitive
              settings={settings}
            />
          )}
          {rateSetting && (
            <OAuthField
              label="Курс USDT (руб.)"
              settingKey="usdt_exchange_rate"
              sensitive={false}
              placeholder="90.5"
              hint="Число, например 90.5"
              settings={settings}
            />
          )}
          {webhookSetting && (
            <WebhookIPsSettingRow
              setting={webhookSetting}
              label="Разрешённые IP вебхуков"
              hint="Один IP на строку. Если пусто — разрешены все IP."
            />
          )}
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

      {settings && (() => {
        const allSettings = settings
        const remnawave = settings.filter(s => REMNAWAVE_KEYS.has(s.key))
        const trial = settings.filter(s => TRIAL_KEYS.has(s.key))
        const emailService = settings.filter(s => EMAIL_SERVICE_KEYS.has(s.key))
        const registration = settings.filter(s => REGISTRATION_KEYS.has(s.key))
        const installSettings = settings.filter(s => s.key.startsWith(INSTALL_KEY_PREFIX))
        const otherSettings = settings.filter(
          s =>
            !REMNAWAVE_KEYS.has(s.key) &&
            !TRIAL_KEYS.has(s.key) &&
            !EMAIL_SERVICE_KEYS.has(s.key) &&
            !REGISTRATION_KEYS.has(s.key) &&
            !PAYMENT_KEYS.has(s.key) &&
            !OAUTH_KEYS.has(s.key) &&
            !s.key.startsWith(INSTALL_KEY_PREFIX),
        )

        // Split remnawave keys into API config vs squad assignments
        const rw_api = remnawave.filter(s => s.key === 'remnawave_url' || s.key === 'remnawave_token')
        const rw_trial_squads = remnawave.filter(s => s.key.startsWith('remnawave_trial_') && s.key.endsWith('_squad_uuids'))
        const rw_paid_squads = remnawave.filter(s => s.key.startsWith('remnawave_paid_') && s.key.endsWith('_squad_uuids'))

        return (
          <div className="space-y-3">
            {/* Remnawave */}
            {remnawave.length > 0 && (
              <CollapsibleSection title="Remnawave" defaultOpen>
                {/* API connection */}
                {rw_api.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-text-muted uppercase tracking-wide px-1">Подключение к API</p>
                    {rw_api.map(s => (
                      <SettingRow
                        key={s.key}
                        setting={s}
                        labelOverride={SETTING_LABELS[s.key]}
                      />
                    ))}
                  </div>
                )}
                {/* Trial squads */}
                {rw_trial_squads.length > 0 && (
                  <div className="space-y-2 pt-2">
                    <p className="text-xs font-medium text-text-muted uppercase tracking-wide px-1">Сквады — Пробный период</p>
                    {rw_trial_squads.map(s => (
                      <SettingRow
                        key={s.key}
                        setting={s}
                        labelOverride={SETTING_LABELS[s.key]}
                        hint={SETTING_HINTS[s.key]}
                      />
                    ))}
                  </div>
                )}
                {/* Paid squads */}
                {rw_paid_squads.length > 0 && (
                  <div className="space-y-2 pt-2">
                    <p className="text-xs font-medium text-text-muted uppercase tracking-wide px-1">Сквады — Платная подписка</p>
                    {rw_paid_squads.map(s => (
                      <SettingRow
                        key={s.key}
                        setting={s}
                        labelOverride={SETTING_LABELS[s.key]}
                        hint={SETTING_HINTS[s.key]}
                      />
                    ))}
                  </div>
                )}
              </CollapsibleSection>
            )}

            {/* Пробный период */}
            {trial.length > 0 && (
              <CollapsibleSection title="Пробный период">
                {trial.map(s =>
                  s.key === 'remnawave_trial_traffic_limit_bytes' ? (
                    <NumberBytesSettingRow
                      key={s.key}
                      setting={s}
                      label={SETTING_LABELS[s.key] ?? s.key}
                    />
                  ) : (
                    <SettingRow key={s.key} setting={s} labelOverride={SETTING_LABELS[s.key]} />
                  ),
                )}
              </CollapsibleSection>
            )}

            {/* Email-сервис */}
            {emailService.length > 0 && (
              <CollapsibleSection title="Email-сервис (Resend)">
                {emailService.map(s => (
                  <SettingRow key={s.key} setting={s} labelOverride={SETTING_LABELS[s.key]} />
                ))}
              </CollapsibleSection>
            )}

            {/* Регистрация */}
            {registration.length > 0 && (
              <CollapsibleSection title="Регистрация">
                {registration.map(s => {
                  if (s.key === 'allowed_email_domains') {
                    return (
                      <TextareaSettingRow
                        key={s.key}
                        setting={s}
                        label={SETTING_LABELS[s.key] ?? s.key}
                        hint="Один домен на строку. Если пусто — разрешены все домены."
                      />
                    )
                  }
                  if (s.key === 'registration_enabled' || s.key === 'email_verification_enabled') {
                    return (
                      <ToggleSettingRow
                        key={s.key}
                        setting={s}
                        label={SETTING_LABELS[s.key] ?? s.key}
                      />
                    )
                  }
                  return <SettingRow key={s.key} setting={s} labelOverride={SETTING_LABELS[s.key]} />
                })}
              </CollapsibleSection>
            )}

            {/* Платёжные системы */}
            <CollapsibleSection title="Платёжные системы">
              <CryptoBotBlock settings={allSettings} />
            </CollapsibleSection>

            {/* OAuth провайдеры */}
            <CollapsibleSection title="OAuth провайдеры">
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
            </CollapsibleSection>

            {/* Приложения */}
            {installSettings.length > 0 && (
              <CollapsibleSection title="Приложения и ссылки">
                {installSettings.map(s => (
                  <SettingRow key={s.key} setting={s} />
                ))}
              </CollapsibleSection>
            )}

            {/* Прочее */}
            {otherSettings.length > 0 && (
              <CollapsibleSection title="Прочее">
                {otherSettings.map(s => (
                  <SettingRow key={s.key} setting={s} />
                ))}
              </CollapsibleSection>
            )}
          </div>
        )
      })()}
    </div>
  )
}

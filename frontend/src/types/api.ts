// src/types/api.ts

export interface ProviderInfo {
  type: string
  username: string | null
  identifier: string | null
}

export interface UserProfile {
  id: string
  display_name: string
  is_admin: boolean
  has_made_payment: boolean
  created_at: string
  providers: ProviderInfo[]
  email_verified: boolean | null   // null = no email provider
}

export interface Plan {
  id: string
  name: string
  label: string
  duration_days: number
  price_rub: number
  new_user_price_rub: number | null
  sort_order: number
}

export interface Transaction {
  id: string
  type: 'trial_activation' | 'payment' | 'promo_bonus' | 'manual'
  status: 'pending' | 'completed' | 'failed'
  amount_rub: number | null
  days_added: number | null
  description: string | null
  created_at: string
  completed_at: string | null
}

export interface PaymentCreateResponse {
  payment_url: string
  transaction_id: string
}

export interface ValidatePromoResponse {
  code: string
  type: 'discount_percent' | 'bonus_days'
  value: number
  already_used: boolean
}

export interface ApplyPromoResponse {
  days_added: number
  new_expires_at: string
}

export interface InstallLinkResponse {
  subscription_url: string
}

export interface ApiError {
  detail: string
}

// Added in Plan 9

export interface SubscriptionResponse {
  type: 'trial' | 'paid'
  status: 'active' | 'expired' | 'disabled'
  started_at: string
  expires_at: string
  traffic_limit_gb: number | null
  days_remaining: number
}

export interface TrialActivateResponse {
  subscription: SubscriptionResponse
  message: string
}

export interface PaymentResponse {
  payment_url: string
  transaction_id: string
  amount_rub: number
  amount_usdt: string
  is_existing: boolean
}

export interface TransactionHistoryItem {
  id: string
  type: 'trial_activation' | 'payment' | 'promo_bonus' | 'manual'
  status: 'pending' | 'completed' | 'failed'
  amount_rub: number | null
  plan_name: string | null
  days_added: number | null
  created_at: string
  completed_at: string | null
}

export interface ArticleListItem {
  id: string
  slug: string
  title: string
  preview_image_url: string | null
  sort_order: number
  created_at: string
}

export interface ArticleDetailResponse extends ArticleListItem {
  content: string
  updated_at: string
}

export interface ApplyPromoRequest {
  code: string
}

export interface CreatePaymentRequest {
  plan_id: string
  promo_code?: string | null
  provider: string
}

// ─── Admin types (Plan 10) ───────────────────────────────────────────────────

// Admin-specific provider info (different from user-facing ProviderInfo)
export interface AdminProviderInfo {
  provider: string
  provider_user_id: string
  provider_username: string | null
  email_verified: boolean | null   // null for OAuth providers
  created_at: string
}

export interface UserAdminListItem {
  id: string
  display_name: string
  avatar_url: string | null
  is_admin: boolean
  is_banned: boolean
  email: string | null
  email_verified: boolean | null
  providers: string[]           // list of provider type strings e.g. ["telegram"]
  subscription_status: string | null
  subscription_type: string | null
  subscription_expires_at: string | null
  remnawave_uuid: string | null
  subscription_conflict: boolean
  has_made_payment: boolean
  created_at: string
  last_seen_at: string
}

export interface PaginatedUsers {
  items: UserAdminListItem[]
  total: number
  page: number
  per_page: number
}

export interface AdminSubscriptionInfo {
  type: string
  status: string
  started_at: string
  expires_at: string
  traffic_limit_gb: number | null
  synced_at: string | null
}

export interface AdminTransactionItem {
  id: string
  type: string
  status: string
  amount_rub: number | null
  days_added: number | null
  description: string | null
  created_at: string
  completed_at: string | null
}

export interface UserAdminDetail {
  id: string
  display_name: string
  avatar_url: string | null
  is_admin: boolean
  is_banned: boolean
  email: string | null
  email_verified: boolean | null
  has_made_payment: boolean
  subscription_conflict: boolean
  remnawave_uuid: string | null
  created_at: string
  last_seen_at: string
  providers: AdminProviderInfo[]
  subscription: AdminSubscriptionInfo | null
  recent_transactions: AdminTransactionItem[]
}

export interface ConflictResolveRequest {
  remnawave_uuid: string
}

export interface SetRemnawaveUuidRequest {
  remnawave_uuid: string
}

export interface SyncAllResponse {
  task_id: string
}

// Backend fields: status, total, done (int), errors (int count)
export interface SyncStatusResponse {
  status: 'running' | 'completed' | 'failed' | 'timed_out'
  total: number
  done: number
  errors: number
}

export interface PlanAdminItem {
  id: string
  name: string
  label: string
  duration_days: number
  price_rub: number
  new_user_price_rub: number | null
  is_active: boolean
  sort_order: number
}

export interface PlanAdminUpdateRequest {
  price_rub?: number
  new_user_price_rub?: number | null
  duration_days?: number
  label?: string
  is_active?: boolean
}

export interface PromoCodeAdminItem {
  id: string
  code: string
  type: 'discount_percent' | 'bonus_days'
  value: number
  max_uses: number | null
  used_count: number
  valid_until: string | null
  is_active: boolean
  created_at: string
}

export interface PromoCodeCreateRequest {
  code: string
  type: 'discount_percent' | 'bonus_days'
  value: number
  max_uses?: number | null
  valid_until?: string | null
}

export interface ArticleAdminListItem {
  id: string
  slug: string
  title: string
  is_published: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface ArticleAdminDetail extends ArticleAdminListItem {
  content: string
  preview_image_url: string | null
}

export interface ArticleAdminCreateRequest {
  slug: string
  title: string
  content: string
  preview_image_url?: string | null
  sort_order?: number
}

export interface ArticleAdminUpdateRequest {
  slug?: string
  title?: string
  content?: string
  preview_image_url?: string | null
  sort_order?: number
}

export interface SettingAdminItem {
  key: string
  value: string | null
  is_sensitive: boolean
  updated_at: string
}

export interface SupportMessageAdminItem {
  id: string
  user_id: string
  display_name: string
  message: string
  created_at: string
}

// Note: support-messages endpoint returns a plain list (no pagination wrapper).
// Use ?skip=N&limit=50 params.

// ─── Plan 11 types ───────────────────────────────────────────────────────────

export interface OAuthConfigResponse {
  google: boolean
  google_client_id: string | null
  vk: boolean
  vk_client_id: string | null
  telegram: boolean
  telegram_bot_username: string | null
  email_enabled: boolean
  support_telegram_url: string | null
  email_verification_required: boolean
}

export interface OsAppConfig {
  app_name: string
  store_url: string
}

export interface InstallAppConfig {
  android: OsAppConfig
  ios: OsAppConfig
  windows: OsAppConfig
  macos: OsAppConfig
  linux: OsAppConfig
}

export interface PlanAdminCreateRequest {
  name: string
  label: string
  duration_days: number
  price_rub: number
  new_user_price_rub?: number | null
  is_active?: boolean
  sort_order?: number
}

export interface PaymentProviderInfo {
  name: string
  label: string
  is_active: boolean
}

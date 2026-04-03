// src/types/api.ts

export interface ProviderInfo {
  type: string
  username: string | null
}

export interface UserProfile {
  id: string
  display_name: string
  is_admin: boolean
  created_at: string
  providers: ProviderInfo[]
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
}

import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Telegram injects TelegramWebviewProxy into its in-app browser WebView on both iOS and Android.
// UA sniffing alone is unreliable on iOS since Telegram intentionally omits its identifier there.
export function isTelegramBrowser(): boolean {
  return (
    typeof (window as unknown as Record<string, unknown>).TelegramWebviewProxy !== 'undefined' ||
    /Telegram-Android/i.test(navigator.userAgent)
  )
}

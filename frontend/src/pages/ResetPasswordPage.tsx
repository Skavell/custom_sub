import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '@/lib/api'
import { AlertCircle, CheckCircle } from 'lucide-react'

function isStrongPassword(p: string) {
  return p.length >= 8 && /[A-Z]/.test(p) && /[a-z]/.test(p) && /[0-9]/.test(p)
}

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token')

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm rounded-card bg-surface p-8 border border-border-neutral text-center space-y-4">
          <AlertCircle className="mx-auto text-red-400" size={40} />
          <p className="text-text-primary font-semibold">Неверная ссылка</p>
          <Link to="/login" className="block text-sm text-accent hover:underline">Войти</Link>
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm rounded-card bg-surface p-8 border border-border-neutral text-center space-y-4">
          <CheckCircle className="mx-auto text-green-400" size={40} />
          <p className="text-text-primary font-semibold">Пароль успешно изменён</p>
          <Link
            to="/login"
            className="block w-full py-2 rounded-input bg-accent text-background font-medium text-sm text-center hover:opacity-90 transition-opacity"
          >
            Войти
          </Link>
        </div>
      </div>
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!isStrongPassword(newPassword)) {
      setError('Пароль должен содержать не менее 8 символов, заглавную букву, строчную букву и цифру')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Пароли не совпадают')
      return
    }

    setLoading(true)
    try {
      await api.post('/api/auth/reset-password/confirm', { token, new_password: newPassword })
      setSuccess(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Ошибка сети')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-card bg-surface p-8 border border-border-neutral">
        <h1 className="text-xl font-bold text-text-primary mb-6">Новый пароль</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-text-secondary mb-1">Новый пароль</label>
            <input
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              required
              className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
              placeholder="Минимум 8 символов"
            />
            {newPassword && !isStrongPassword(newPassword) && (
              <p className="mt-1 text-xs text-text-muted">Мин. 8 символов, заглавная буква, строчная буква, цифра</p>
            )}
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Повторите пароль</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
              className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
              placeholder="Повторите новый пароль"
            />
            {confirmPassword && newPassword !== confirmPassword && (
              <p className="mt-1 text-xs text-red-400">Пароли не совпадают</p>
            )}
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 rounded-input bg-accent text-background font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {loading ? 'Сохранение...' : 'Сохранить пароль'}
          </button>
        </form>
      </div>
    </div>
  )
}

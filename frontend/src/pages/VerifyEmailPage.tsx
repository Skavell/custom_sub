import { useSearchParams, Link } from 'react-router-dom'
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react'

export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const verified = params.get('verified')
  const error = params.get('error')

  if (verified === '1') {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-4">
        <div className="max-w-sm w-full text-center space-y-6">
          <CheckCircle className="mx-auto text-green-400" size={48} />
          <h1 className="text-xl font-semibold text-text-primary">Email подтверждён</h1>
          <p className="text-sm text-text-secondary">
            Ваш адрес электронной почты успешно подтверждён. Теперь вы можете активировать пробный период.
          </p>
          <Link
            to="/subscription"
            className="inline-block w-full py-2.5 px-4 rounded-input bg-accent text-background text-sm font-semibold text-center hover:bg-accent/90 transition-colors"
          >
            Перейти к подписке
          </Link>
        </div>
      </div>
    )
  }

  if (error === 'expired') {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-4">
        <div className="max-w-sm w-full text-center space-y-6">
          <XCircle className="mx-auto text-red-400" size={48} />
          <h1 className="text-xl font-semibold text-text-primary">Ссылка устарела</h1>
          <p className="text-sm text-text-secondary">
            Ссылка для подтверждения недействительна или истекла. Запросите новую ссылку на главной странице.
          </p>
          <Link
            to="/"
            className="inline-block w-full py-2.5 px-4 rounded-input bg-surface border border-border-neutral text-text-primary text-sm font-semibold text-center hover:border-accent transition-colors"
          >
            На главную
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="max-w-sm w-full text-center space-y-6">
        <AlertCircle className="mx-auto text-text-muted" size={48} />
        <h1 className="text-xl font-semibold text-text-primary">Неверная ссылка</h1>
        <p className="text-sm text-text-secondary">
          Эта ссылка недействительна.
        </p>
        <Link
          to="/"
          className="inline-block w-full py-2.5 px-4 rounded-input bg-surface border border-border-neutral text-text-primary text-sm font-semibold text-center hover:border-accent transition-colors"
        >
          На главную
        </Link>
      </div>
    </div>
  )
}

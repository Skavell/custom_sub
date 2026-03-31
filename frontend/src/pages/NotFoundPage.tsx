import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center px-4">
      <h1 className="text-4xl font-bold text-text-primary">404</h1>
      <p className="text-text-secondary">Страница не найдена</p>
      <Link to="/" className="text-accent hover:underline text-sm">
        На главную
      </Link>
    </div>
  )
}

import { Outlet, NavLink, Link } from 'react-router-dom'
import {
  Users, RefreshCw, CreditCard, Tag, BookOpen, Settings, MessageSquare,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'

const ADMIN_NAV = [
  { to: '/admin/users', label: 'Пользователи', icon: Users },
  { to: '/admin/sync', label: 'Синхронизация', icon: RefreshCw },
  { to: '/admin/plans', label: 'Тарифы', icon: CreditCard },
  { to: '/admin/promo-codes', label: 'Промокоды', icon: Tag },
  { to: '/admin/articles', label: 'Статьи', icon: BookOpen },
  { to: '/admin/settings', label: 'Настройки', icon: Settings },
  { to: '/admin/support-messages', label: 'Сообщения', icon: MessageSquare },
] as const

export default function AdminLayout() {
  const { user } = useAuth()

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-[220px] flex-col border-r border-border-neutral bg-surface px-4 py-6 shrink-0">
        <div className="mb-1 px-3">
          <span className="text-lg font-bold bg-gradient-to-r from-accent to-accent-hover bg-clip-text text-transparent">
            Skavellion
          </span>
        </div>
        <div className="mb-6 px-3">
          <span className="text-xs text-text-muted">Панель администратора</span>
        </div>
        <nav className="flex flex-col gap-1 flex-1">
          {ADMIN_NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-input px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-accent/10 text-accent'
                    : 'text-text-secondary hover:bg-white/5 hover:text-text-primary',
                )
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <Link
          to="/"
          className="mt-2 flex items-center gap-2 rounded-input px-3 py-2 text-xs text-text-muted hover:text-text-primary transition-colors"
        >
          ← На сайт
        </Link>
        {user && (
          <div className="mt-2 flex items-center gap-2 rounded-input px-3 py-2 bg-white/5">
            <div className="h-7 w-7 rounded-full bg-accent/20 flex items-center justify-center text-xs font-medium text-accent">
              {user.display_name[0].toUpperCase()}
            </div>
            <span className="text-xs text-text-secondary truncate">{user.display_name}</span>
          </div>
        )}
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 inset-x-0 z-50 border-b border-border-neutral bg-surface px-4 py-3 flex items-center gap-3 overflow-x-auto">
        {ADMIN_NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-1.5 shrink-0 text-xs font-medium px-2 py-1 rounded-input transition-colors',
                isActive ? 'text-accent bg-accent/10' : 'text-text-muted',
              )
            }
          >
            <Icon size={14} />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>

      {/* Main content */}
      <main className="flex-1 overflow-auto pt-14 md:pt-0 pb-4">
        <Outlet />
      </main>
    </div>
  )
}

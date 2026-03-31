import { Outlet, NavLink } from 'react-router-dom'
import { Home, CreditCard, Download, BookOpen, MessageCircle, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'

const NAV_ITEMS = [
  { to: '/', label: 'Главная', icon: Home, exact: true },
  { to: '/subscription', label: 'Подписка', icon: CreditCard, exact: false },
  { to: '/install', label: 'Установка', icon: Download, exact: false },
  { to: '/docs', label: 'Документация', icon: BookOpen, exact: false },
  { to: '/support', label: 'Поддержка', icon: MessageCircle, exact: false },
  { to: '/profile', label: 'Профиль', icon: User, exact: false },
] as const

type NavItemProps = (typeof NAV_ITEMS)[number]

function NavItem({ to, label, icon: Icon, exact }: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={exact}
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
  )
}

export default function Layout() {
  const { user } = useAuth()

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-[220px] flex-col border-r border-border-neutral bg-surface px-4 py-6 shrink-0">
        {/* Logo */}
        <div className="mb-8 px-3">
          <span className="text-lg font-bold bg-gradient-to-r from-accent to-accent-hover bg-clip-text text-transparent">
            Skavellion
          </span>
        </div>
        {/* Nav */}
        <nav className="flex flex-col gap-1 flex-1">
          {NAV_ITEMS.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}
        </nav>
        {/* User badge */}
        {user && (
          <div className="mt-4 flex items-center gap-2 rounded-input px-3 py-2 bg-white/5">
            <div className="h-7 w-7 rounded-full bg-accent/20 flex items-center justify-center text-xs font-medium text-accent">
              {user.display_name[0].toUpperCase()}
            </div>
            <span className="text-xs text-text-secondary truncate">{user.display_name}</span>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto pb-20 md:pb-0">
        <Outlet />
      </main>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 border-t border-border-neutral bg-surface flex items-center justify-around px-2 py-2 z-50">
        {NAV_ITEMS.map(({ to, label, icon: Icon, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              cn(
                'flex flex-col items-center gap-0.5 px-2 py-1 rounded-input text-xs transition-colors',
                isActive ? 'text-accent' : 'text-text-muted',
              )
            }
          >
            <Icon size={20} />
            <span className="text-[10px]">{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

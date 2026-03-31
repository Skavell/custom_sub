import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { UserProfile } from '@/types/api'

export function useAuth() {
  const { data: user, isLoading, error } = useQuery<UserProfile>({
    queryKey: ['me'],
    queryFn: () => api.get<UserProfile>('/api/users/me'),
    retry: false,
    staleTime: 60_000,
  })

  return {
    user: user ?? null,
    isLoading,
    isAuthenticated: !!user,
    isAdmin: user?.is_admin ?? false,
    error,
  }
}

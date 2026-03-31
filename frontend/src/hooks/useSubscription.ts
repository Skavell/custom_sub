import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import type { Subscription } from '@/types/api'

export function useSubscription() {
  return useQuery<Subscription | null>({
    queryKey: ['subscription'],
    queryFn: async () => {
      try {
        return await api.get<Subscription>('/api/subscriptions/me')
      } catch (e: unknown) {
        if (e instanceof ApiError && e.status === 404) {
          return null
        }
        throw e
      }
    },
    staleTime: 30_000,
  })
}

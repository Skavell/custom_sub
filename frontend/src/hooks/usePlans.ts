import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Plan } from '@/types/api'

export function usePlans() {
  return useQuery<Plan[]>({
    queryKey: ['plans'],
    queryFn: () => api.get<Plan[]>('/api/plans'),
    staleTime: 5 * 60_000,
  })
}

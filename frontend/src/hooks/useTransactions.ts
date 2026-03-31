import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { TransactionHistoryItem } from '@/types/api'

export function useTransactions() {
  return useQuery<TransactionHistoryItem[]>({
    queryKey: ['transactions'],
    queryFn: () => api.get<TransactionHistoryItem[]>('/api/payments/history'),
    staleTime: 30_000,
  })
}

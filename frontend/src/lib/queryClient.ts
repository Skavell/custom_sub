import { QueryClient } from '@tanstack/react-query'
import { ApiError } from './api'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error: unknown) => {
        if (error instanceof ApiError) {
          if (error.status === 401 || error.status === 403) return false
        }
        return failureCount < 2
      },
    },
  },
})

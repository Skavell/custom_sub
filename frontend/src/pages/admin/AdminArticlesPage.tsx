// frontend/src/pages/admin/AdminArticlesPage.tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, Pencil, Trash2, Eye, EyeOff } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { ArticleAdminListItem } from '@/types/api'

export default function AdminArticlesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: articles, isLoading, error } = useQuery<ArticleAdminListItem[]>({
    queryKey: ['admin-articles'],
    queryFn: () => api.get<ArticleAdminListItem[]>('/api/admin/articles'),
    staleTime: 30_000,
  })

  const publishMutation = useMutation({
    mutationFn: ({ id, publish }: { id: string; publish: boolean }) =>
      api.post(`/api/admin/articles/${id}/${publish ? 'publish' : 'unpublish'}`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-articles'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/admin/articles/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-articles'] }),
  })

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-bold text-text-primary">Статьи</h1>
        <button
          onClick={() => navigate('/admin/articles/new')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-accent text-background text-xs font-medium hover:bg-accent-hover transition-colors"
        >
          <Plus size={14} /> Создать
        </button>
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400">
          {error instanceof ApiError ? error.detail : 'Ошибка загрузки'}
        </p>
      )}

      <div className="flex flex-col gap-1">
        {articles?.map((article) => (
          <div
            key={article.id}
            className="flex items-center gap-3 rounded-input bg-surface border border-border-neutral px-4 py-3"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-text-primary truncate">
                  {article.title}
                </span>
                {!article.is_published && (
                  <span className="text-xs bg-white/5 text-text-muted px-1.5 py-0.5 rounded shrink-0">
                    черновик
                  </span>
                )}
              </div>
              <span className="text-xs text-text-muted font-mono">{article.slug}</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() =>
                  publishMutation.mutate({ id: article.id, publish: !article.is_published })
                }
                disabled={publishMutation.isPending}
                title={article.is_published ? 'Снять с публикации' : 'Опубликовать'}
                className="p-1.5 rounded-input text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
              >
                {article.is_published ? (
                  <EyeOff size={14} />
                ) : (
                  <Eye size={14} className="text-accent" />
                )}
              </button>
              <button
                onClick={() => navigate(`/admin/articles/${article.id}/edit`)}
                className="p-1.5 rounded-input text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={() => {
                  if (confirm(`Удалить статью "${article.title}"?`))
                    deleteMutation.mutate(article.id)
                }}
                disabled={deleteMutation.isPending}
                className="p-1.5 rounded-input text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
        {articles?.length === 0 && (
          <p className="text-sm text-text-muted text-center py-8">Статьи не найдены</p>
        )}
      </div>
    </div>
  )
}

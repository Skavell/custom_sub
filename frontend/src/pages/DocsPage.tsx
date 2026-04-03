import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import type { ArticleListItem } from '@/types/api'

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

export default function DocsPage() {
  const { data: articles = [], isLoading } = useQuery<ArticleListItem[]>({
    queryKey: ['articles'],
    queryFn: () => api.get<ArticleListItem[]>('/api/articles'),
    staleTime: 5 * 60_000,
  })

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-1">Документация</h1>
      <p className="text-sm text-text-muted mb-5">Руководства и инструкции</p>

      {isLoading ? (
        <div className="flex justify-center py-10">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      ) : articles.length === 0 ? (
        <div className="rounded-card bg-surface border border-border-neutral p-8 text-center">
          <BookOpen size={32} className="mx-auto text-text-muted mb-3" />
          <p className="text-sm text-text-muted">Статьи появятся здесь</p>
        </div>
      ) : (
        <div className="space-y-3">
          {articles.map((article) => (
            <Link
              key={article.id}
              to={`/docs/${article.slug}`}
              className="group flex items-center gap-4 rounded-card bg-surface border border-border-neutral p-4 hover:border-accent/40 transition-colors"
            >
              {article.preview_image_url ? (
                <img
                  src={article.preview_image_url}
                  alt=""
                  className="h-14 w-20 rounded-input object-cover shrink-0"
                />
              ) : (
                <div className="h-14 w-20 rounded-input bg-accent/10 flex items-center justify-center shrink-0">
                  <BookOpen size={20} className="text-accent" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-text-primary group-hover:text-accent transition-colors truncate">
                  {article.title}
                </p>
                <p className="text-xs text-text-muted mt-0.5">{formatDate(article.created_at)}</p>
              </div>
              <ChevronRight size={16} className="text-text-muted shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

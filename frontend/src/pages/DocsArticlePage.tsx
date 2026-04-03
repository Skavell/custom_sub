import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api, ApiError } from '@/lib/api'
import type { ArticleDetailResponse } from '@/types/api'

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

export default function DocsArticlePage() {
  const { slug } = useParams<{ slug: string }>()

  const { data: article, isLoading, error } = useQuery<ArticleDetailResponse>({
    queryKey: ['article', slug],
    queryFn: () => api.get<ArticleDetailResponse>(`/api/articles/${slug}`),
    enabled: !!slug,
    retry: false,
  })

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <Link
        to="/docs"
        className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary mb-5 transition-colors"
      >
        <ArrowLeft size={14} />
        Назад
      </Link>

      {isLoading && (
        <div className="flex justify-center py-10">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-card bg-red-500/10 border border-red-500/20 p-5 text-sm text-red-400">
          {error instanceof ApiError && error.status === 404
            ? 'Статья не найдена'
            : 'Ошибка загрузки статьи'}
        </div>
      )}

      {article && (
        <>
          <h1 className="text-2xl font-bold text-text-primary mb-2">{article.title}</h1>
          <p className="text-xs text-text-muted mb-6">Обновлено {formatDate(article.updated_at)}</p>
          <div className="
            [&_h1]:text-xl [&_h1]:font-bold [&_h1]:text-text-primary [&_h1]:mt-6 [&_h1]:mb-3
            [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-text-primary [&_h2]:mt-5 [&_h2]:mb-2
            [&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-text-primary [&_h3]:mt-4 [&_h3]:mb-2
            [&_p]:text-text-secondary [&_p]:leading-relaxed [&_p]:mb-3
            [&_a]:text-accent [&_a]:no-underline hover:[&_a]:underline
            [&_code]:bg-white/10 [&_code]:text-accent [&_code]:rounded [&_code]:px-1 [&_code]:text-sm
            [&_pre]:bg-surface [&_pre]:border [&_pre]:border-border-neutral [&_pre]:rounded-card [&_pre]:p-4 [&_pre]:overflow-x-auto [&_pre]:mb-4
            [&_pre_code]:bg-transparent [&_pre_code]:text-text-secondary [&_pre_code]:p-0
            [&_blockquote]:border-l-2 [&_blockquote]:border-accent/40 [&_blockquote]:pl-4 [&_blockquote]:text-text-muted [&_blockquote]:italic [&_blockquote]:mb-3
            [&_strong]:text-text-primary [&_strong]:font-semibold
            [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_ul]:text-text-secondary
            [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-3 [&_ol]:text-text-secondary
            [&_li]:mb-1
            [&_hr]:border-border-neutral [&_hr]:my-6
            [&_table]:w-full [&_table]:text-sm [&_table]:mb-4
            [&_th]:text-left [&_th]:text-text-primary [&_th]:font-semibold [&_th]:pb-2 [&_th]:border-b [&_th]:border-border-neutral
            [&_td]:py-2 [&_td]:pr-4 [&_td]:text-text-secondary [&_td]:border-b [&_td]:border-border-neutral/50
          ">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{article.content}</ReactMarkdown>
          </div>
        </>
      )}
    </div>
  )
}

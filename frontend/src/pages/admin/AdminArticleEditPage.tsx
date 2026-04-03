// frontend/src/pages/admin/AdminArticleEditPage.tsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowLeft, Eye, Code } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type {
  ArticleAdminDetail,
  ArticleAdminCreateRequest,
  ArticleAdminUpdateRequest,
} from '@/types/api'

export default function AdminArticleEditPage() {
  const { id } = useParams<{ id?: string }>()
  const isNew = !id
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [preview, setPreview] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [form, setForm] = useState({
    slug: '',
    title: '',
    content: '',
    preview_image_url: '',
    sort_order: 0,
  })

  const { data: existing, isLoading } = useQuery<ArticleAdminDetail>({
    queryKey: ['admin-article', id],
    queryFn: () => api.get<ArticleAdminDetail>(`/api/admin/articles/${id}`),
    enabled: !isNew,
  })

  useEffect(() => {
    if (existing) {
      setForm({
        slug: existing.slug,
        title: existing.title,
        content: existing.content,
        preview_image_url: existing.preview_image_url ?? '',
        sort_order: existing.sort_order,
      })
    }
  }, [existing])

  const createMutation = useMutation({
    mutationFn: (data: ArticleAdminCreateRequest) =>
      api.post<ArticleAdminDetail>('/api/admin/articles', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-articles'] })
      navigate('/admin/articles')
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка создания'),
  })

  const updateMutation = useMutation({
    mutationFn: (data: ArticleAdminUpdateRequest) =>
      api.patch<ArticleAdminDetail>(`/api/admin/articles/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-articles'] })
      queryClient.invalidateQueries({ queryKey: ['admin-article', id] })
      navigate('/admin/articles')
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка сохранения'),
  })

  function handleSave() {
    setSaveError(null)
    const payload = {
      slug: form.slug,
      title: form.title,
      content: form.content,
      preview_image_url: form.preview_image_url || null,
      sort_order: form.sort_order,
    }
    if (isNew) {
      createMutation.mutate(payload)
    } else {
      updateMutation.mutate(payload)
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  if (!isNew && isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-5 gap-3">
        <button
          onClick={() => navigate('/admin/articles')}
          className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft size={15} /> Назад
        </button>
        <h1 className="text-lg font-bold text-text-primary">
          {isNew ? 'Новая статья' : 'Редактировать статью'}
        </h1>
        <button
          onClick={handleSave}
          disabled={isSaving || !form.slug || !form.title || !form.content}
          className="px-4 py-1.5 rounded-input bg-accent text-background text-sm font-medium disabled:opacity-50 hover:bg-accent-hover transition-colors"
        >
          {isSaving ? 'Сохранение...' : 'Сохранить'}
        </button>
      </div>

      {/* Meta fields */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Slug (URL)</span>
          <input
            value={form.slug}
            onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
            placeholder="kak-podklyuchitsya"
            className="rounded-input bg-surface border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent font-mono"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Порядок сортировки</span>
          <input
            type="number"
            value={form.sort_order}
            onChange={(e) => setForm((f) => ({ ...f, sort_order: Number(e.target.value) }))}
            className="rounded-input bg-surface border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="col-span-2 flex flex-col gap-1">
          <span className="text-xs text-text-muted">Заголовок</span>
          <input
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            placeholder="Как подключиться к туннелю"
            className="rounded-input bg-surface border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="col-span-2 flex flex-col gap-1">
          <span className="text-xs text-text-muted">URL превью-изображения</span>
          <input
            value={form.preview_image_url}
            onChange={(e) => setForm((f) => ({ ...f, preview_image_url: e.target.value }))}
            placeholder="https://..."
            className="rounded-input bg-surface border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
      </div>

      {/* Editor / Preview toggle */}
      <div className="flex items-center gap-2 mb-2">
        <button
          onClick={() => setPreview(false)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-input text-xs transition-colors ${
            !preview ? 'bg-accent/10 text-accent' : 'text-text-muted hover:text-text-primary'
          }`}
        >
          <Code size={13} /> Редактор
        </button>
        <button
          onClick={() => setPreview(true)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-input text-xs transition-colors ${
            preview ? 'bg-accent/10 text-accent' : 'text-text-muted hover:text-text-primary'
          }`}
        >
          <Eye size={13} /> Предпросмотр
        </button>
      </div>

      {!preview ? (
        <textarea
          value={form.content}
          onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
          placeholder="# Заголовок&#10;&#10;Текст статьи в Markdown..."
          rows={24}
          className="w-full rounded-card bg-surface border border-border-neutral px-4 py-3 text-sm text-text-primary placeholder:text-text-muted font-mono focus:outline-none focus:border-accent resize-y"
        />
      ) : (
        <div className="w-full rounded-card bg-surface border border-border-neutral px-4 py-3 min-h-[400px] prose prose-invert prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{form.content || '*Контент пуст*'}</ReactMarkdown>
        </div>
      )}

      {saveError && <p className="mt-2 text-xs text-red-400">{saveError}</p>}
    </div>
  )
}

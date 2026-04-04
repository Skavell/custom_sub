import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '@/lib/api'

export default function VKCallbackPage() {
  const navigate = useNavigate()
  const called = useRef(false)

  useEffect(() => {
    if (called.current) return
    called.current = true

    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const error = params.get('error')

    if (error || !code) {
      navigate('/login', { replace: true })
      return
    }

    const redirectUri = `${window.location.origin}/auth/vk/callback`
    const deviceId = localStorage.getItem('vk_device_id') ?? ''
    const state = localStorage.getItem('vk_state') ?? ''
    const intent = localStorage.getItem('oauth_intent')

    localStorage.removeItem('vk_device_id')
    localStorage.removeItem('vk_state')
    localStorage.removeItem('oauth_intent')

    const payload = { code, redirect_uri: redirectUri, device_id: deviceId, state }
    const endpoint = intent === 'link'
      ? '/api/users/me/providers/vk'
      : '/api/auth/oauth/vk'
    const successPath = intent === 'link' ? '/profile' : '/'

    api
      .post(endpoint, payload)
      .then(() => navigate(successPath, { replace: true }))
      .catch((e) => {
        console.error('VK OAuth failed', e instanceof ApiError ? e.detail : e)
        navigate(intent === 'link' ? '/profile' : '/login', { replace: true })
      })
  }, [navigate])

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
    </div>
  )
}

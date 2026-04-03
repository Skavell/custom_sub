import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/Layout'
import ProtectedRoute from '@/components/ProtectedRoute'
import AdminRoute from '@/components/AdminRoute'
import AdminLayout from '@/components/AdminLayout'
import LoginPage from '@/pages/LoginPage'
import HomePage from '@/pages/HomePage'
import SubscriptionPage from '@/pages/SubscriptionPage'
import InstallPage from '@/pages/InstallPage'
import DocsPage from '@/pages/DocsPage'
import DocsArticlePage from '@/pages/DocsArticlePage'
import SupportPage from '@/pages/SupportPage'
import ProfilePage from '@/pages/ProfilePage'
import NotFoundPage from '@/pages/NotFoundPage'
import AdminUsersPage from '@/pages/admin/AdminUsersPage'
import AdminUserDetailPage from '@/pages/admin/AdminUserDetailPage'
import AdminSyncPage from '@/pages/admin/AdminSyncPage'
import AdminPlansPage from '@/pages/admin/AdminPlansPage'
import AdminPromoCodesPage from '@/pages/admin/AdminPromoCodesPage'
import AdminArticlesPage from '@/pages/admin/AdminArticlesPage'
import AdminArticleEditPage from '@/pages/admin/AdminArticleEditPage'
import AdminSettingsPage from '@/pages/admin/AdminSettingsPage'
import AdminSupportMessagesPage from '@/pages/admin/AdminSupportMessagesPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        {/* Admin routes */}
        <Route element={<AdminRoute />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />
            <Route path="/admin/users/:id" element={<AdminUserDetailPage />} />
            <Route path="/admin/sync" element={<AdminSyncPage />} />
            <Route path="/admin/plans" element={<AdminPlansPage />} />
            <Route path="/admin/promo-codes" element={<AdminPromoCodesPage />} />
            <Route path="/admin/articles" element={<AdminArticlesPage />} />
            <Route path="/admin/articles/new" element={<AdminArticleEditPage />} />
            <Route path="/admin/articles/:id/edit" element={<AdminArticleEditPage />} />
            <Route path="/admin/settings" element={<AdminSettingsPage />} />
            <Route path="/admin/support-messages" element={<AdminSupportMessagesPage />} />
          </Route>
        </Route>

        {/* User routes */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/subscription" element={<SubscriptionPage />} />
            <Route path="/install" element={<InstallPage />} />
            <Route path="/docs" element={<DocsPage />} />
            <Route path="/docs/:slug" element={<DocsArticlePage />} />
            <Route path="/support" element={<SupportPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

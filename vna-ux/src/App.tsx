import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { queryClient } from '@/lib/api'
import Layout from '@/components/Layout'
import { ToastProvider } from '@/components/Toast'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import DashboardPage from '@/pages/DashboardPage'
import ArchiveBrowserPage from '@/pages/ArchiveBrowserPage'
import LabelsPage from '@/pages/LabelsPage'
import ViewerPage from '@/pages/ViewerPage'

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<DashboardPage />} />
                <Route path="archive" element={<ArchiveBrowserPage />} />
                <Route path="labels" element={<LabelsPage />} />
                <Route path="viewer/:id" element={<ViewerPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </ErrorBoundary>
    </QueryClientProvider>
  )
}

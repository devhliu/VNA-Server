import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useArchiveResource } from '@/hooks/useArchive'
import { Loader2 } from 'lucide-react'

export default function ViewerPage() {
  const { id } = useParams<{ id: string }>()
  const { data: resource, isLoading } = useArchiveResource(id ?? '')
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [contentLoading, setContentLoading] = useState(false)

  useEffect(() => {
    if (!id || !resource) return

    const ext = resource.name.split('.').pop()?.toLowerCase()
    if (['json', 'txt', 'csv', 'tsv'].includes(ext ?? '')) {
      setContentLoading(true)
      fetch(`/bids-api/files/${id}`)
        .then(res => res.text())
        .then(text => setFileContent(text))
        .catch(() => setFileContent('Failed to load file content'))
        .finally(() => setContentLoading(false))
    }
  }, [id, resource])

  const renderViewer = () => {
    if (!resource) return null

    const ext = resource.name.split('.').pop()?.toLowerCase()

    if (['png', 'jpg', 'jpeg', 'tif', 'tiff'].includes(ext ?? '')) {
      return <img src={`/bids-api/files/${id}`} alt={resource.name} className="max-w-full" loading="lazy" />
    }

    if (ext === 'pdf') {
      return <iframe src={`/bids-api/files/${id}`} className="w-full h-[700px]" title={resource.name} sandbox="allow-same-origin allow-scripts" />
    }

    if (['json', 'txt', 'csv', 'tsv'].includes(ext ?? '')) {
      return (
        <pre className="bg-gray-900 text-green-400 p-6 rounded-lg font-mono text-sm overflow-auto max-h-[600px]">
          {contentLoading ? 'Loading...' : fileContent}
        </pre>
      )
    }

    return (
      <div className="text-center py-12 text-gray-500">
        No preview available for this file format
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Document Viewer</h1>
          {resource && <p className="text-sm text-gray-500 mt-0.5">{resource.name}</p>}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-32 bg-white rounded-xl border border-gray-200 shadow-sm">
          <Loader2 className="animate-spin text-blue-600" size={36} />
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          {renderViewer()}
        </div>
      )}
    </div>
  )
}

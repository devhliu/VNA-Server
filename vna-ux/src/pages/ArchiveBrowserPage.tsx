import { useState, useMemo, useCallback } from 'react'
import { useArchiveChildren, useUpdateItemTags } from '@/hooks/useArchive'
import { ChevronRight, Folder, Search, LayoutGrid, Table, Database, Plus, Play } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { GalleryView } from '@/components/gallery/GalleryView'

interface ArchiveItem {
  id: string
  name: string
  type: string
  thumbnail?: string
  modality?: string
  created_at: string
  size_bytes?: number
  tags: string[]
  has_children: boolean
}

const BYTE_UNITS = [
  { threshold: 1024 ** 3, suffix: 'GB' },
  { threshold: 1024 ** 2, suffix: 'MB' },
  { threshold: 1024, suffix: 'KB' },
] as const

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  for (const unit of BYTE_UNITS) {
    if (bytes >= unit.threshold) return `${(bytes / unit.threshold).toFixed(2)} ${unit.suffix}`
  }
  return `${bytes} B`
}

export default function ArchiveBrowserPage() {
  const [selectedId, setSelectedId] = useState<string | undefined>()
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState<'gallery' | 'table'>('gallery')
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(new Set())
  const { data: items, isLoading, isError, refetch } = useArchiveChildren(selectedId)
  const updateTags = useUpdateItemTags()

  const filteredItems = useMemo(() => {
    if (!items) return []
    if (!search.trim()) return items
    const q = search.toLowerCase()
    return items.filter(item => item.name.toLowerCase().includes(q))
  }, [items, search]) as ArchiveItem[]

  const handleItemDoubleClick = useCallback((item: ArchiveItem) => {
    if (item.has_children) {
      setSelectedId(item.id)
    }
  }, [])

  const handleItemTagChange = useCallback((itemId: string, tags: string[]) => {
    updateTags.mutate({ id: itemId, tags })
  }, [updateTags])

  return (
    <div className="space-y-4 h-[calc(100vh-8rem)] flex flex-col">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Data Management</h1>
          <p className="text-gray-500 mt-1">Browse, tag and manage archive resources</p>
        </div>
        <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as 'gallery' | 'table')}>
          <TabsList>
            <TabsTrigger value="gallery" className="flex items-center gap-1">
              <LayoutGrid className="w-4 h-4" />
              Gallery
            </TabsTrigger>
            <TabsTrigger value="table" className="flex items-center gap-1">
              <Table className="w-4 h-4" />
              Table
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Dataset Management Bar */}
      <div className="flex items-center gap-2 p-2 bg-white border border-gray-200 rounded-lg">
        <Button variant="ghost" size="sm" className="flex items-center gap-1">
          <Database className="w-4 h-4" />
          Dataset: Default
        </Button>
        <div className="h-4 w-px bg-gray-200" />
        <Button variant="ghost" size="sm" className="flex items-center gap-1">
          <Plus className="w-4 h-4" />
          Create Dataset
        </Button>
        <Button variant="ghost" size="sm">
          Add to Dataset
        </Button>
        <Button variant="ghost" size="sm" className="flex items-center gap-1">
          <Play className="w-4 h-4" />
          Run Workflow
        </Button>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Search: modality:MR patient:sub-00* -label:Exclude"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        />
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 gap-4 min-h-0">
        {/* Metadata Sidebar */}
        <div className="w-44 shrink-0 bg-white border border-gray-200 rounded-lg p-3 overflow-auto">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Metadata</h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-gray-500">Items</span>
              <span className="font-medium">{filteredItems.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Selected</span>
              <span className="font-medium">{selectedItemIds.size || filteredItems.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Total Size</span>
              <span className="font-medium">{formatBytes(filteredItems.reduce((sum, i) => sum + (i.size_bytes || 0), 0))}</span>
            </div>
          </div>
        </div>

        {/* Main View */}
        <div className="flex-1 bg-white border border-gray-200 rounded-lg overflow-hidden flex flex-col min-w-0">
          {/* Breadcrumb */}
          <div className="px-4 py-2 border-b border-gray-200 flex items-center gap-2 text-sm">
            <span className="text-gray-500">/</span>
            {selectedId ? (
              <>
                <button onClick={() => { setSelectedId(undefined); setSearch('') }} className="text-blue-600 hover:underline">
                  Root
                </button>
                <ChevronRight size={14} className="text-gray-400 shrink-0" />
                <span className="text-gray-700 truncate">{selectedId}</span>
              </>
            ) : (
              <span className="text-gray-700">Root</span>
            )}
          </div>

          {isLoading ? (
            <div className="p-5 space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-32 w-32 inline-block mr-4" />
              ))}
            </div>
          ) : isError ? (
            <div className="p-8 text-center">
              <p className="text-gray-500 mb-3">Failed to load archive</p>
              <Button variant="outline" size="sm" onClick={() => refetch()}>Retry</Button>
            </div>
          ) : filteredItems.length ? (
            <GalleryView
              items={filteredItems}
              onItemDoubleClick={handleItemDoubleClick}
              onSelectionChange={setSelectedItemIds}
              onItemTagChange={handleItemTagChange}
            />
          ) : (
            <div className="py-12 text-center text-gray-500 text-sm flex-1 flex items-center justify-center">
              <div>
                <Folder size={40} className="mx-auto mb-3 text-gray-300" />
                {search ? 'No items match your search' : 'No items found in this location'}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

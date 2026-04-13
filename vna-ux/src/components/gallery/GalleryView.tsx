import { useState, useCallback, useEffect, useMemo } from 'react'
import { GalleryCard } from './GalleryCard'
import { TagBar } from './TagBar'
import { useLabels } from '@/hooks/useLabels'

interface GalleryItem {
  id: string
  name: string
  type: string
  thumbnail?: string
  modality?: string
  created_at: string
  size_bytes?: number
  tags: string[]
}

interface GalleryViewProps {
  items: GalleryItem[]
  onItemDoubleClick: (item: GalleryItem) => void
  onSelectionChange: (selectedIds: Set<string>) => void
  onItemTagChange?: (itemId: string, tags: string[]) => void
}

export function GalleryView({ items, onItemDoubleClick, onSelectionChange, onItemTagChange }: GalleryViewProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [activeTags, setActiveTags] = useState<string[]>([])
  const [multiTagMode, setMultiTagMode] = useState(false)
  const [lastClickedIndex, setLastClickedIndex] = useState<number | null>(null)

  const { data: availableTags = [] } = useLabels()

  // Implicit select all: empty selection means all items are selected
  const effectiveSelection = useMemo(() => {
    if (selectedIds.size === 0) {
      return new Set(items.map(i => i.id))
    }
    return selectedIds
  }, [selectedIds, items])

  useEffect(() => {
    onSelectionChange(effectiveSelection)
  }, [effectiveSelection, onSelectionChange])

  const handleItemClick = useCallback((e: React.MouseEvent, item: GalleryItem, index: number) => {
    e.preventDefault()

    // If there are active tags, apply tag instead of selecting
    if (activeTags.length > 0 && onItemTagChange) {
      const currentTags = item.tags
      const hasAllActiveTags = activeTags.every(tag => currentTags.includes(tag))

      let newTags: string[]
      if (hasAllActiveTags) {
        // Remove all active tags
        newTags = currentTags.filter(t => !activeTags.includes(t))
      } else {
        // Add missing active tags
        newTags = [...new Set([...currentTags, ...activeTags])]
      }

      onItemTagChange(item.id, newTags)

      // Clear active tag if not in multi mode
      if (!multiTagMode) {
        setActiveTags([])
      }
      return
    }

    // Normal selection logic
    const isCtrlClick = e.ctrlKey || e.metaKey
    const isShiftClick = e.shiftKey

    if (isShiftClick && lastClickedIndex !== null) {
      // Range selection
      const start = Math.min(lastClickedIndex, index)
      const end = Math.max(lastClickedIndex, index)
      const rangeIds = items.slice(start, end + 1).map(i => i.id)

      if (isCtrlClick) {
        // Add range to existing selection
        const newSelection = new Set(selectedIds)
        rangeIds.forEach(id => newSelection.add(id))
        setSelectedIds(newSelection)
      } else {
        // Replace selection with range
        setSelectedIds(new Set(rangeIds))
      }
    } else if (isCtrlClick) {
      // Toggle single item
      const newSelection = new Set(selectedIds)
      if (newSelection.has(item.id)) {
        newSelection.delete(item.id)
      } else {
        newSelection.add(item.id)
      }
      setSelectedIds(newSelection)
    } else {
      // Single select
      setSelectedIds(new Set([item.id]))
    }

    setLastClickedIndex(index)
  }, [selectedIds, lastClickedIndex, items, activeTags, multiTagMode, onItemTagChange])

  const handleTagToggle = useCallback((tag: string) => {
    setActiveTags(prev => {
      if (prev.includes(tag)) {
        return prev.filter(t => t !== tag)
      }
      if (multiTagMode) {
        return [...prev, tag]
      }
      return [tag]
    })
  }, [multiTagMode])

  const handleTagCreate = useCallback((tag: string) => {
    // Create tag via hook will be handled by useLabels mutation
    setActiveTags([tag])
  }, [])

  // Clear selection on background click
  const handleBackgroundClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      setSelectedIds(new Set())
      setLastClickedIndex(null)
    }
  }, [])

  return (
    <div className="flex flex-col h-full">
      <TagBar
        availableTags={availableTags}
        activeTags={activeTags}
        onTagToggle={handleTagToggle}
        onTagCreate={handleTagCreate}
        multiTagMode={multiTagMode}
        onMultiTagToggle={() => setMultiTagMode(prev => !prev)}
      />

      {/* Selection count indicator */}
      <div className="px-4 py-1.5 text-xs text-gray-500 bg-gray-50 border-b border-gray-200">
        {selectedIds.size === 0
          ? `${items.length} items selected (implicit all)`
          : `${selectedIds.size} of ${items.length} items selected`
        }
        {activeTags.length > 0 && (
          <span className="ml-3 text-emerald-600">
            Active tag{activeTags.length > 1 ? 's' : ''}: {activeTags.join(', ')}
          </span>
        )}
      </div>

      <div
        className="flex-1 overflow-auto p-4"
        onClick={handleBackgroundClick}
      >
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-4">
          {items.map((item, index) => (
            <GalleryCard
              key={item.id}
              item={item}
              isSelected={selectedIds.has(item.id)}
              isActiveTagTarget={activeTags.length > 0}
              onClick={(e) => handleItemClick(e, item, index)}
              onDoubleClick={() => onItemDoubleClick(item)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

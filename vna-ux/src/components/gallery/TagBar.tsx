import { useState, useCallback, useEffect } from 'react'
import { Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface TagBarProps {
  availableTags: string[]
  activeTags: string[]
  onTagToggle: (tag: string) => void
  onTagCreate: (tag: string) => void
  multiTagMode: boolean
  onMultiTagToggle: () => void
}

export function TagBar({
  availableTags,
  activeTags,
  onTagToggle,
  onTagCreate,
  multiTagMode,
  onMultiTagToggle
}: TagBarProps) {
  const [isAdding, setIsAdding] = useState(false)
  const [newTag, setNewTag] = useState('')

  // Keyboard shortcuts for first 5 tags
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const num = parseInt(e.key)
      if (num >= 1 && num <= 5 && availableTags.length >= num) {
        e.preventDefault()
        onTagToggle(availableTags[num - 1])
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [availableTags, onTagToggle])

  const handleCreateTag = useCallback(() => {
    if (newTag.trim()) {
      onTagCreate(newTag.trim())
      setNewTag('')
      setIsAdding(false)
    }
  }, [newTag, onTagCreate])

  return (
    <div className="flex items-center gap-2 p-2 bg-white border-b border-gray-200 overflow-x-auto">
      {availableTags.map((tag, index) => (
        <button
          key={tag}
          onClick={() => onTagToggle(tag)}
          className={cn(
            "flex items-center gap-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors whitespace-nowrap",
            activeTags.includes(tag)
              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
              : "bg-gray-100 text-gray-700 hover:bg-gray-200 border border-transparent"
          )}
        >
          <span className="w-4 text-xs text-gray-400">{index < 5 ? index + 1 : ''}</span>
          {tag}
          {activeTags.includes(tag) && <X className="w-3 h-3 ml-1" />}
        </button>
      ))}

      {isAdding ? (
        <div className="flex items-center gap-1">
          <input
            autoFocus
            type="text"
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreateTag()}
            onBlur={() => {
              if (!newTag.trim()) setIsAdding(false)
            }}
            className="px-2 py-1 text-sm border border-gray-300 rounded-md w-32 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="New tag..."
          />
          <Button size="sm" variant="ghost" onClick={handleCreateTag}>
            Add
          </Button>
        </div>
      ) : (
        <button
          onClick={() => setIsAdding(true)}
          className="flex items-center gap-1 px-2 py-1.5 rounded-md text-sm text-gray-500 hover:bg-gray-100"
        >
          <Plus className="w-4 h-4" />
          Add Tag
        </button>
      )}

      <div className="ml-auto">
        <Button
          variant="ghost"
          size="sm"
          onClick={onMultiTagToggle}
          className={cn(
            "text-xs",
            multiTagMode && "bg-blue-100 text-blue-800 hover:bg-blue-200"
          )}
        >
          Tag Mode: {multiTagMode ? 'Multi' : 'Single'}
        </Button>
      </div>
    </div>
  )
}

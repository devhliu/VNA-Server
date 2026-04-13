import { useState } from 'react'
import { Check, Eye, File } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

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

interface GalleryCardProps {
  item: GalleryItem
  isSelected: boolean
  isActiveTagTarget: boolean
  onClick: (e: React.MouseEvent) => void
  onDoubleClick: () => void
}

export function GalleryCard({ item, isSelected, isActiveTagTarget, onClick, onDoubleClick }: GalleryCardProps) {
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div
      className={cn(
        "relative rounded-lg border bg-white cursor-pointer transition-all duration-150 overflow-hidden group",
        isSelected && "ring-2 ring-blue-500 border-blue-500",
        isActiveTagTarget && !isSelected && "ring-2 ring-emerald-400 border-emerald-400",
        isHovered && !isSelected && !isActiveTagTarget && "border-gray-400 shadow-md",
      )}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Thumbnail Container */}
      <div className="aspect-square bg-gray-100 relative overflow-hidden">
        {item.thumbnail ? (
          <img
            src={item.thumbnail}
            alt={item.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <File className="w-12 h-12 text-gray-300" />
          </div>
        )}

        {/* Selection Checkmark */}
        {isSelected && (
          <div className="absolute top-2 left-2 w-5 h-5 bg-blue-500 rounded flex items-center justify-center shadow">
            <Check className="w-3 h-3 text-white" />
          </div>
        )}

        {/* Hover actions */}
        {isHovered && !isSelected && (
          <div className="absolute top-2 right-2">
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDoubleClick()
              }}
              className="w-7 h-7 bg-black/50 hover:bg-black/70 rounded flex items-center justify-center text-white transition-colors"
            >
              <Eye className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Tag badges overlay */}
        {item.tags.length > 0 && (
          <div className="absolute bottom-2 left-2 right-2 flex flex-wrap gap-1">
            {item.tags.slice(0, 3).map(tag => (
              <Badge key={tag} variant="secondary" className="text-xs py-0 px-1.5 bg-black/60 text-white border-0">
                {tag}
              </Badge>
            ))}
            {item.tags.length > 3 && (
              <Badge variant="secondary" className="text-xs py-0 px-1.5 bg-black/60 text-white border-0">
                +{item.tags.length - 3}
              </Badge>
            )}
          </div>
        )}
      </div>

      {/* Card content */}
      <div className="p-2 space-y-1">
        <p className="text-sm font-medium text-gray-900 truncate">{item.name}</p>
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{item.modality || item.type}</span>
          <span>{new Date(item.created_at).toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  )
}

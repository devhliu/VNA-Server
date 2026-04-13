import { useQuery } from '@tanstack/react-query'
import { fetchApi } from '@/lib/api'

export interface ArchiveResource {
  id: string
  type: 'patient' | 'study' | 'series' | 'file'
  name: string
  created_at: string
  file_format?: string
  size_bytes?: number
  has_children: boolean
  labels: string[]
}

export function useArchiveChildren(parentId?: string) {
  return useQuery({
    queryKey: ['archive', parentId || 'root'],
    queryFn: () => fetchApi<ArchiveResource[]>(parentId ? `/api/v1/resources?parent=${parentId}` : '/api/v1/resources'),
  })
}

export function useArchiveResource(id: string) {
  return useQuery({
    queryKey: ['archive', id],
    queryFn: () => fetchApi<ArchiveResource>(`/api/v1/resources/${id}`),
  })
}

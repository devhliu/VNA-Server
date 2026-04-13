import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi } from '@/lib/api'

export interface Label {
  id: string
  name: string
  description?: string
  color: string
  created_at: string
  usage_count: number
}

export interface ActivityEvent {
  id: string
  message: string
  timestamp: string
  type?: string
}

export function useLabels() {
  return useQuery({
    queryKey: ['labels'],
    queryFn: () => fetchApi<Label[]>('/api/v1/labels/tags'),
  })
}

export function useCreateLabel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (label: Partial<Label>) => fetchApi('/api/v1/labels/tags', {
      method: 'POST',
      body: JSON.stringify(label)
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['labels'] })
  })
}

export function useDeleteLabel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => fetchApi(`/api/v1/labels/tags/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['labels'] })
  })
}

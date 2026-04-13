import { useQuery } from '@tanstack/react-query'
import { fetchApi } from '@/lib/api'

export interface ServiceStatus {
  service: string
  status: 'healthy' | 'degraded' | 'down'
  uptime: number
  latency: number
  last_check: string
}

export interface SystemMetrics {
  total_studies: number
  total_patients: number
  storage_used_bytes: number
  storage_total_bytes: number
  jobs_pending: number
  jobs_running: number
  jobs_failed: number
}

export interface ActivityEvent {
  id: string
  message: string
  timestamp: string
  type?: string
}

export interface ActivityEvent {
  id: string
  message: string
  timestamp: string
  type?: string
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ['system', 'status'],
    queryFn: () => fetchApi<ServiceStatus[]>('/system/status'),
    refetchInterval: 15000,
  })
}

export function useSystemMetrics() {
  return useQuery({
    queryKey: ['system', 'metrics'],
    queryFn: () => fetchApi<SystemMetrics>('/system/metrics'),
    refetchInterval: 60000,
  })
}

export function useRecentActivity() {
  return useQuery({
    queryKey: ['system', 'activity'],
    queryFn: () => fetchApi<ActivityEvent[]>('/system/activity?limit=20'),
    refetchInterval: 30000,
  })
}

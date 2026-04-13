import { useSystemStatus, useSystemMetrics, useRecentActivity, type ActivityEvent } from '@/hooks/useSystemStatus'
import { Activity, HardDrive, Folder, Clock, AlertCircle, CheckCircle, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const BYTE_UNITS = [
  { threshold: 1024 ** 4, suffix: 'TB' },
  { threshold: 1024 ** 3, suffix: 'GB' },
  { threshold: 1024 ** 2, suffix: 'MB' },
  { threshold: 1024, suffix: 'KB' },
] as const

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  for (const unit of BYTE_UNITS) {
    if (bytes >= unit.threshold) {
      return `${(bytes / unit.threshold).toFixed(2)} ${unit.suffix}`
    }
  }
  return `${bytes} B`
}

const statusIcons = {
  healthy: <CheckCircle className="text-green-600" size={16} />,
  degraded: <AlertCircle className="text-amber-600" size={16} />,
  down: <XCircle className="text-red-600" size={16} />,
} as const

const badgeClasses: Record<string, string> = {
  healthy: 'bg-green-50 text-green-700',
  degraded: 'bg-amber-50 text-amber-700',
  down: 'bg-red-50 text-red-700',
}

function MetricCard({ label, value, icon, color = 'blue' }: { label: string; value: string; icon: React.ReactNode; color?: 'blue' | 'green' | 'amber' | 'red' }) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
  }

  return (
    <Card className="shadow-sm hover:shadow-md transition-shadow duration-200">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-gray-500 font-medium">{label}</p>
            <p className="text-2xl font-semibold text-gray-900 mt-2">{value}</p>
          </div>
          <div className={cn('flex items-center justify-center w-12 h-12 rounded-xl shrink-0', colorClasses[color])}>
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function MetricSkeleton() {
  return <Skeleton className="h-20 w-full rounded-lg" />
}

export default function DashboardPage() {
  const { data: services, isLoading: statusLoading, isError: statusError, refetch: refetchStatus } = useSystemStatus()
  const { data: metrics, isLoading: metricsLoading } = useSystemMetrics()
  const { data: activity, isLoading: activityLoading } = useRecentActivity()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">System overview and health status</p>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {metricsLoading ? (
          <>
            <MetricSkeleton />
            <MetricSkeleton />
            <MetricSkeleton />
            <MetricSkeleton />
          </>
        ) : (
          <>
            <MetricCard
              label="Total Studies"
              value={metrics?.total_studies?.toLocaleString() ?? '0'}
              icon={<Folder size={22} />}
              color="blue"
            />
            <MetricCard
              label="Patients"
              value={metrics?.total_patients?.toLocaleString() ?? '0'}
              icon={<HardDrive size={22} />}
              color="green"
            />
            <MetricCard
              label="Storage Used"
              value={formatBytes(metrics?.storage_used_bytes ?? 0)}
              icon={<HardDrive size={22} />}
              color="amber"
            />
            <MetricCard
              label="Active Jobs"
              value={String(metrics?.jobs_running ?? 0)}
              icon={<Activity size={22} />}
              color="blue"
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Service Status */}
        <Card>
          <CardHeader className="px-5 py-4 border-b">
            <h3 className="font-medium">Service Status</h3>
          </CardHeader>
          <CardContent className="p-4 space-y-3">
            {statusLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : statusError ? (
              <div className="text-center py-4">
                <p className="text-sm text-gray-500 mb-2">Failed to load status</p>
                <Button variant="outline" size="sm" onClick={() => refetchStatus()}>Retry</Button>
              </div>
            ) : services?.length ? services.map((srv) => (
              <div key={srv.service} className="flex items-center justify-between py-2">
                <div className="flex items-center gap-3">
                  {statusIcons[srv.status] ?? <Activity className="text-gray-400" size={16} />}
                  <span className="text-sm font-medium">{srv.service}</span>
                </div>
                <Badge variant="outline" className={cn('text-xs px-2 py-0.5', badgeClasses[srv.status])}>
                  {srv.status}
                </Badge>
              </div>
            )) : (
              <div className="text-sm text-gray-500 py-4 text-center">No status data</div>
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card className="lg:col-span-2">
          <CardHeader className="px-5 py-4 border-b">
            <h3 className="font-medium">Recent Activity</h3>
          </CardHeader>
          <CardContent className="p-4">
            {activityLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : activity?.length ? (
              <div className="space-y-3">
                {activity.slice(0, 8).map((event: ActivityEvent) => (
                  <div key={event.id ?? event.timestamp} className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
                    <Clock size={14} className="text-gray-400 mt-0.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-900">{event.message}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{new Date(event.timestamp).toLocaleString()}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500 py-8 text-center">No recent activity</div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

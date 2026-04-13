import { useState } from 'react'
import { useLabels, useCreateLabel, useDeleteLabel } from '@/hooks/useLabels'
import { Plus, Trash2, Loader2 } from 'lucide-react'
import { useToast } from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

export default function LabelsPage() {
  const { data: labels, isLoading, isError, refetch } = useLabels()
  const createLabel = useCreateLabel()
  const deleteLabel = useDeleteLabel()
  const { success, error: showError } = useToast()

  const [newLabel, setNewLabel] = useState({ name: '', description: '', color: '#3b82f6' })
  const [showForm, setShowForm] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newLabel.name.trim()) return

    createLabel.mutate(newLabel, {
      onSuccess: () => {
        success('Label created', `"${newLabel.name}" has been added`)
        setNewLabel({ name: '', description: '', color: '#3b82f6' })
        setShowForm(false)
      },
      onError: (err) => {
        showError('Failed to create label', err.message)
      }
    })
  }

  const handleDelete = (id: string, name: string) => {
    deleteLabel.mutate(id, {
      onSuccess: () => {
        success('Label deleted', `"${name}" has been removed`)
        setDeleteConfirm(null)
      },
      onError: (err) => {
        showError('Failed to delete label', err.message)
      }
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Labels</h1>
          <p className="text-gray-500 mt-1">Manage archive labels and classification</p>
        </div>
        <Button onClick={() => setShowForm(true)}>
          <Plus size={16} />
          New Label
        </Button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                required
                placeholder="e.g. processed, raw, qc-pass"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={newLabel.name}
                onChange={e => setNewLabel({ ...newLabel, name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <input
                type="text"
                placeholder="Optional description"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={newLabel.description}
                onChange={e => setNewLabel({ ...newLabel, description: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Color</label>
              <input
                type="color"
                className="w-full h-10 border border-gray-300 rounded-md"
                value={newLabel.color}
                onChange={e => setNewLabel({ ...newLabel, color: e.target.value })}
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowForm(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createLabel.isPending}>
              {createLabel.isPending && <Loader2 size={14} className="animate-spin" />}
              {createLabel.isPending ? 'Creating...' : 'Create Label'}
            </Button>
          </div>
        </form>
      )}

      {deleteConfirm && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Trash2 size={18} className="text-amber-600" />
            <span className="text-sm text-amber-800">
              Delete label <strong>{labels?.find(l => l.id === deleteConfirm)?.name}</strong>? This cannot be undone.
            </span>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setDeleteConfirm(null)}>
              Cancel
            </Button>
            <Button variant="destructive" size="sm" onClick={() => handleDelete(deleteConfirm, '')}>
              Delete
            </Button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-lg" />
            ))}
          </div>
        ) : isError ? (
          <div className="p-8 text-center">
            <p className="text-gray-500 mb-3">Failed to load labels</p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>Retry</Button>
          </div>
        ) : (
          <Table>
            <TableHeader className="bg-gray-50">
              <TableRow>
                <TableHead className="h-12 px-6 font-medium">Label</TableHead>
                <TableHead className="h-12 px-6 font-medium">Description</TableHead>
                <TableHead className="h-12 px-6 font-medium text-right">Usage</TableHead>
                <TableHead className="h-12 px-6 font-medium text-right w-16"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {labels?.length ? labels.map(label => (
                <TableRow key={label.id} className="h-16 hover:bg-gray-50 transition-colors">
                  <TableCell className="px-6">
                    <div className="flex items-center gap-3">
                      <div className="w-5 h-5 rounded-full shadow-sm" style={{ backgroundColor: label.color }} />
                      <span className="font-medium text-gray-900">{label.name}</span>
                      <Badge variant="secondary" className="text-xs">{label.color}</Badge>
                    </div>
                  </TableCell>
                  <TableCell className="px-6 text-gray-600">{label.description || '-'}</TableCell>
                  <TableCell className="px-6 text-right text-gray-600">{label.usage_count} items</TableCell>
                  <TableCell className="px-6 text-right">
                    <button
                      onClick={() => setDeleteConfirm(label.id)}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      aria-label={`Delete label ${label.name}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </TableCell>
                </TableRow>
              )) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-12 text-gray-500">
                    No labels created yet
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}

import React from 'react'
import { useAppStore } from '../store/appStore'
import { X, Upload, FileJson, FileText } from 'lucide-react'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog'

export const ImportModal: React.FC = () => {
  const importModalOpen = useAppStore((s) => s.importModalOpen)
  const setImportModalOpen = useAppStore((s) => s.setImportModalOpen)
  const setFilaments = useAppStore((s) => s.setFilaments)
  const setCustomLibraryLoaded = useAppStore((s) => s.setCustomLibraryLoaded)
  const activeTab = useAppStore((s) => s.activeTab)

  const [dragOver, setDragOver] = React.useState(false)
  const [importStatus, setImportStatus] = React.useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (ext !== 'json' && ext !== 'csv') {
      setImportStatus({ type: 'error', message: 'Only JSON and CSV files are supported' })
      return
    }

    const reader = new FileReader()
    reader.onload = async () => {
      const text = reader.result as string

      try {
        let response: Response

        if (ext === 'csv') {
          response = await fetch('/api/filaments/import-csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contents: text }),
          })
        } else {
          const data = JSON.parse(text)
          const arr = Array.isArray(data) ? data : [data]

          response = await fetch('/api/filaments/import-json', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(arr),
          })
        }

        const data = await response.json()

        if (data.status === 'ok') {
          setImportStatus({ type: 'success', message: data.message })
          setCustomLibraryLoaded(true)

          const params = new URLSearchParams()
          if (activeTab) params.set('filament_type', activeTab)
          const refetch = await fetch(`/api/filaments?${params.toString()}`)
          const filaments = await refetch.json()
          setFilaments(filaments)
        } else {
          setImportStatus({ type: 'error', message: data.message || 'Import failed' })
        }
      } catch (err) {
        setImportStatus({ type: 'error', message: `Import failed: ${err}` })
      }
    }

    reader.readAsText(file)
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) {
      await handleFile(file)
    }
  }

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      await handleFile(file)
    }
  }

  const handleClose = () => {
    setImportModalOpen(false)
    setImportStatus(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <Dialog open={importModalOpen} onOpenChange={setImportModalOpen}>
      <DialogContent data-testid="import-modal">
        <div className="bg-gray-900 rounded-lg w-full flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <DialogTitle className="text-sm font-semibold text-gray-200 flex items-center gap-2 leading-none tracking-normal">
            <Upload className="w-4 h-4" />
            Import Filaments
          </DialogTitle>
          <DialogDescription className="sr-only">
            Import filaments from a JSON or CSV file by dropping or browsing for it.
          </DialogDescription>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-200"
            data-testid="close-import"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              dragOver ? 'border-blue-500 bg-blue-500/10' : 'border-gray-600 hover:border-gray-500'
            }`}
          >
            <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
            <p className="text-sm text-gray-300 mb-1">Drop a file here or click to browse</p>
            <p className="text-xs text-gray-500">Supports JSON and CSV formats</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,.csv"
              onChange={handleFileInput}
              className="hidden"
              data-testid="file-input"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="mt-3 px-4 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-200"
            >
              Browse Files
            </button>
          </div>

          <div className="flex gap-3">
            <div className="flex-1 flex items-center gap-2 p-3 bg-gray-800 rounded">
              <FileJson className="w-5 h-5 text-blue-400" />
              <div>
                <p className="text-xs text-gray-200 font-medium">JSON</p>
                <p className="text-xs text-gray-500">AutoForge format</p>
              </div>
            </div>
            <div className="flex-1 flex items-center gap-2 p-3 bg-gray-800 rounded">
              <FileText className="w-5 h-5 text-green-400" />
              <div>
                <p className="text-xs text-gray-200 font-medium">CSV</p>
                <p className="text-xs text-gray-500">Spreadsheet format</p>
              </div>
            </div>
          </div>

          {importStatus && (
            <div className={`p-3 rounded text-xs ${
              importStatus.type === 'success'
                ? 'bg-green-900/30 text-green-300 border border-green-700'
                : 'bg-red-900/30 text-red-300 border border-red-700'
            }`}>
              {importStatus.message}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-gray-700">
            <button
              onClick={handleClose}
              className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-200"
            >
              Close
            </button>
          </div>
        </div>
      </div>
      </DialogContent>
    </Dialog>
  )
}

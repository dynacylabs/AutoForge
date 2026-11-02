import React from 'react'
import { useAppStore } from '../store/appStore'
import { refreshLibrary } from '../services/filamentService'
import { describeApiError } from '../lib/apiError'
import { parseHexInput } from '../lib/color'
import { X, ListPlus, Plus, Trash2, ClipboardPaste } from 'lucide-react'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog'
import { NumberInput } from './ui/number-input'

interface Row {
  id: number
  brand: string
  name: string
  color: string
  td: number
  filamentType: string
  owned: boolean
}

let nextId = 1
const blankRow = (filamentType: string): Row => ({
  id: nextId++,
  brand: '',
  name: '',
  color: '#ffffff',
  td: 5,
  filamentType,
  owned: true,
})

/** Splits pasted lines (comma or tab separated, as copied from a spreadsheet
 * or typed by hand) into rows. Field order is flexible: whichever token
 * looks like a hex color becomes the color, whichever looks like a plain
 * number becomes the TD, and whatever's left is brand/name in that order. */
function parsePastedRows(text: string, filamentType: string): Row[] {
  const rows: Row[] = []
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line) continue
    const fields = line.split(/\t|,/).map((f) => f.trim()).filter((f) => f.length > 0)
    if (fields.length === 0) continue

    let color = ''
    let td: number | null = null
    const rest: string[] = []
    for (const field of fields) {
      // Check the plain-number case first: a bare "123" is ambiguous with a
      // 3-digit hex shorthand, and a TD value is far more likely.
      if (td === null && /^-?\d+(\.\d+)?$/.test(field)) {
        td = parseFloat(field)
        continue
      }
      if (!color && parseHexInput(field)) {
        color = field.startsWith('#') ? field : `#${field}`
        continue
      }
      rest.push(field)
    }

    const row = blankRow(filamentType)
    if (color) row.color = parseHexInput(color) ? color : row.color
    if (td !== null) row.td = td
    if (rest.length >= 2) {
      row.brand = rest[0]
      row.name = rest.slice(1).join(' ')
    } else if (rest.length === 1) {
      row.name = rest[0]
    }
    if (row.name || row.brand) rows.push(row)
  }
  return rows
}

export const BulkAddFilamentsModal: React.FC = () => {
  const open = useAppStore((s) => s.bulkAddModalOpen)
  const setOpen = useAppStore((s) => s.setBulkAddModalOpen)
  const activeTab = useAppStore((s) => s.activeTab)
  const setCustomLibraryLoaded = useAppStore((s) => s.setCustomLibraryLoaded)
  const pushToast = useAppStore((s) => s.pushToast)

  const [rows, setRows] = React.useState<Row[]>(() => [blankRow(activeTab), blankRow(activeTab), blankRow(activeTab)])
  const [pasteOpen, setPasteOpen] = React.useState(false)
  const [pasteText, setPasteText] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const reset = () => {
    setRows([blankRow(activeTab), blankRow(activeTab), blankRow(activeTab)])
    setPasteOpen(false)
    setPasteText('')
    setError(null)
  }

  const updateRow = (id: number, patch: Partial<Row>) => setRows((r) => r.map((row) => (row.id === id ? { ...row, ...patch } : row)))
  const removeRow = (id: number) => setRows((r) => r.filter((row) => row.id !== id))
  const addRow = () => setRows((r) => [...r, blankRow(activeTab)])

  const applyPaste = () => {
    const parsed = parsePastedRows(pasteText, activeTab)
    if (parsed.length === 0) {
      setError('Could not find any filaments in that text — one per line, with a name and TD at least.')
      return
    }
    setRows((r) => [...r.filter((row) => row.brand || row.name), ...parsed])
    setPasteOpen(false)
    setPasteText('')
    setError(null)
  }

  const handleSubmit = async () => {
    const usable = rows.filter((r) => r.name.trim() || r.brand.trim())
    if (usable.length === 0) {
      setError('Enter at least one filament (a name and TD, at minimum).')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const payload = usable.map((r) => ({
        brand: r.brand.trim(),
        name: r.name.trim() || r.brand.trim(),
        color: r.color,
        td: r.td,
        filament_type: r.filamentType.trim(),
        owned: r.owned,
        source: 'user',
      }))
      const response = await fetch('/api/filaments/import-json?mode=merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await response.json().catch(() => null)
      if (!response.ok || data?.status !== 'ok') {
        throw new Error(describeApiError(data, response.status))
      }
      setCustomLibraryLoaded(true)
      await refreshLibrary(activeTab)
      pushToast(`Added ${usable.length} filament${usable.length === 1 ? '' : 's'} to your library`)
      setOpen(false)
      reset()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset() }}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col p-0 gap-0 bg-gray-900 border-gray-700" data-testid="bulk-add-modal">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <DialogTitle className="text-sm font-semibold text-gray-200 flex items-center gap-2 leading-none tracking-normal">
            <ListPlus className="w-4 h-4" />
            Add Your Filaments
          </DialogTitle>
          <DialogDescription className="sr-only">
            Enter several filaments at once — brand, name, color and transmission distance (TD) — without importing a file.
          </DialogDescription>
          <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-200" aria-label="Close" data-testid="close-bulk-add">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          <p className="text-xs text-gray-400">
            List the filaments you actually have, with their TD (transmission distance). No HueForge file needed —
            these go straight into your library and can be marked active for the optimizer.
          </p>

          <div className="flex justify-between items-center">
            <button
              type="button"
              onClick={() => setPasteOpen((v) => !v)}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs border border-gray-600 text-gray-300 hover:bg-gray-800"
              data-testid="bulk-add-paste-toggle"
            >
              <ClipboardPaste className="w-3.5 h-3.5" /> Paste a list instead
            </button>
          </div>

          {pasteOpen && (
            <div className="p-3 bg-gray-800 rounded space-y-2" data-testid="bulk-add-paste-area">
              <p className="text-xs text-gray-400">
                One filament per line: brand, name, color, TD in any order (comma or tab separated) — e.g.{' '}
                <code className="text-gray-300">Bambu Lab, Jade White, #ffffff, 5</code>
              </p>
              <textarea
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                rows={5}
                className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-gray-200 font-mono focus:outline-none focus:border-blue-500"
                placeholder={'Bambu Lab, Jade White, #ffffff, 5\nPolymaker, Blue, #1e90ff, 3.2'}
                data-testid="bulk-add-paste-textarea"
              />
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setPasteOpen(false)} className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-200">
                  Cancel
                </button>
                <button type="button" onClick={applyPaste} className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-xs text-white" data-testid="bulk-add-paste-apply">
                  Add to table below
                </button>
              </div>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-xs" data-testid="bulk-add-table">
              <thead>
                <tr className="text-gray-400 text-left">
                  <th className="pb-1 pr-2 font-medium">Brand</th>
                  <th className="pb-1 pr-2 font-medium">Name</th>
                  <th className="pb-1 pr-2 font-medium">Type</th>
                  <th className="pb-1 pr-2 font-medium">Color</th>
                  <th className="pb-1 pr-2 font-medium">TD</th>
                  <th className="pb-1 pr-2 font-medium">Owned</th>
                  <th className="pb-1" />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} data-testid="bulk-add-row">
                    <td className="pr-2 py-1">
                      <input
                        type="text"
                        value={row.brand}
                        onChange={(e) => updateRow(row.id, { brand: e.target.value })}
                        placeholder="Brand"
                        className="w-full bg-gray-800 border border-gray-600 rounded px-1.5 py-1 text-gray-200 focus:outline-none focus:border-blue-500"
                        data-testid="bulk-add-brand"
                      />
                    </td>
                    <td className="pr-2 py-1">
                      <input
                        type="text"
                        value={row.name}
                        onChange={(e) => updateRow(row.id, { name: e.target.value })}
                        placeholder="Name"
                        className="w-full bg-gray-800 border border-gray-600 rounded px-1.5 py-1 text-gray-200 focus:outline-none focus:border-blue-500"
                        data-testid="bulk-add-name"
                      />
                    </td>
                    <td className="pr-2 py-1">
                      <input
                        type="text"
                        value={row.filamentType}
                        onChange={(e) => updateRow(row.id, { filamentType: e.target.value })}
                        placeholder="PLA"
                        className="w-20 bg-gray-800 border border-gray-600 rounded px-1.5 py-1 text-gray-200 focus:outline-none focus:border-blue-500"
                        data-testid="bulk-add-type"
                      />
                    </td>
                    <td className="pr-2 py-1">
                      <div className="flex items-center gap-1">
                        <input
                          type="color"
                          value={row.color}
                          onChange={(e) => updateRow(row.id, { color: e.target.value })}
                          className="w-6 h-6 rounded cursor-pointer flex-shrink-0"
                          data-testid="bulk-add-color-swatch"
                        />
                        <input
                          type="text"
                          value={row.color}
                          onChange={(e) => updateRow(row.id, { color: e.target.value })}
                          className="w-20 bg-gray-800 border border-gray-600 rounded px-1.5 py-1 text-gray-200 font-mono focus:outline-none focus:border-blue-500"
                          data-testid="bulk-add-color-hex"
                        />
                      </div>
                    </td>
                    <td className="pr-2 py-1">
                      <NumberInput
                        value={row.td}
                        onValueChange={(v) => updateRow(row.id, { td: v })}
                        step={0.1}
                        min={0}
                        className="w-16 bg-gray-800 border border-gray-600 rounded px-1.5 py-1 text-gray-200 focus:outline-none focus:border-blue-500"
                        data-testid="bulk-add-td"
                      />
                    </td>
                    <td className="pr-2 py-1 text-center">
                      <input
                        type="checkbox"
                        checked={row.owned}
                        onChange={(e) => updateRow(row.id, { owned: e.target.checked })}
                        data-testid="bulk-add-owned"
                      />
                    </td>
                    <td className="py-1">
                      <button
                        type="button"
                        onClick={() => removeRow(row.id)}
                        className="p-1 text-gray-500 hover:text-red-400"
                        aria-label="Remove row"
                        data-testid="bulk-add-remove-row"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button
            type="button"
            onClick={addRow}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs border border-gray-600 text-gray-300 hover:bg-gray-800"
            data-testid="bulk-add-add-row"
          >
            <Plus className="w-3.5 h-3.5" /> Add Row
          </button>

          {error && (
            <div className="p-2 rounded text-xs bg-red-900/30 text-red-300 border border-red-700" data-testid="bulk-add-error">
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 px-4 py-3 border-t border-gray-700">
          <button type="button" onClick={() => setOpen(false)} className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-200">
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-xs text-white"
            data-testid="bulk-add-submit"
          >
            {submitting ? 'Adding…' : 'Add to Library'}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

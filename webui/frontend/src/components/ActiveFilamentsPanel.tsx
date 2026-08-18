import React from 'react'
import { useAppStore } from '../store/appStore'
import { Minus, AlertTriangle } from 'lucide-react'

export const ActiveFilamentsPanel: React.FC = () => {
  const activeFilaments = useAppStore((s) => s.activeFilaments)
  const removeActiveFilament = useAppStore((s) => s.removeActiveFilament)
  const inputImage = useAppStore((s) => s.inputImage)
  const runInit = useAppStore((s) => s.runInit)

  const handleRemove = (uuid: string) => {
    removeActiveFilament(uuid)
  }

  // When first filament is added and we have an image, trigger init
  React.useEffect(() => {
    if (activeFilaments.length === 1 && inputImage) {
      runInit()
    }
  }, [activeFilaments.length, inputImage, runInit])

  return (
    <div className="border-b border-gray-700">
      <div className="px-3 py-2 border-b border-gray-700 bg-gray-800/50">
        <h2 className="text-xs font-semibold text-gray-200">Active Filaments</h2>
      </div>

      {activeFilaments.length === 0 ? (
        <div className="px-3 py-4 text-center">
          <AlertTriangle className="w-4 h-4 text-yellow-500 mx-auto mb-1" />
          <p className="text-xs text-yellow-400">No active filaments</p>
          <p className="text-xs text-gray-500 mt-1">Add filaments from the library below</p>
        </div>
      ) : (
        <div className="max-h-48 overflow-y-auto" data-testid="active-filaments-list">
          {activeFilaments.map((f) => (
            <div
              key={f.uuid}
              className="flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-gray-800 border-b border-gray-800/50"
              data-testid={`active-filament-${f.uuid}`}
            >
              <button
                onClick={() => handleRemove(f.uuid)}
                className="flex-shrink-0 w-4 h-4 flex items-center justify-center text-red-400 hover:text-red-300 hover:bg-red-900/30 rounded"
                data-testid={`remove-filament-${f.uuid}`}
              >
                <Minus className="w-3 h-3" />
              </button>
              <div
                className="w-3 h-3 rounded border border-gray-600 flex-shrink-0"
                style={{ backgroundColor: f.color }}
              />
              <span className="text-gray-300 truncate flex-1">{f.name}</span>
              <span className="text-xs font-mono flex-shrink-0 text-gray-500">
                TD: {f.td}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

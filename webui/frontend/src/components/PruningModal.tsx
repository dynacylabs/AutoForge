import React, { useState } from 'react'
import { useAppStore } from '../store/appStore'
import { X, Play } from 'lucide-react'

export const PruningModal: React.FC = () => {
  const pruningModalOpen = useAppStore((s) => s.pruningModalOpen)
  const setPruningModalOpen = useAppStore((s) => s.setPruningModalOpen)
  const pruningSettings = useAppStore((s) => s.pruningSettings)
  const setPruningSettings = useAppStore((s) => s.setPruningSettings)
  const startPruning = useAppStore((s) => s.startPruning)

  const [localSettings, setLocalSettings] = useState(pruningSettings)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    setPruningSettings(localSettings)
    setError(null)
    try {
      await startPruning()
      setPruningModalOpen(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start pruning')
      console.error('Failed to start pruning:', e)
    }
  }

  if (!pruningModalOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-gray-800 rounded-lg shadow-xl w-96 max-w-[90vw]" data-testid="pruning-modal">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <h2 className="text-sm font-semibold text-gray-100">Pruning Settings</h2>
          <button
            onClick={() => setPruningModalOpen(false)}
            className="text-gray-400 hover:text-gray-200"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Max Colors
            </label>
            <input
              type="number"
              value={localSettings.pruning_max_colors}
              onChange={(e) =>
                setLocalSettings({
                  ...localSettings,
                  pruning_max_colors: parseInt(e.target.value) || 100,
                })
              }
              className="w-full text-sm bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-gray-200 focus:outline-none focus:border-blue-500"
              min={1}
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Max Swaps
            </label>
            <input
              type="number"
              value={localSettings.pruning_max_swaps}
              onChange={(e) =>
                setLocalSettings({
                  ...localSettings,
                  pruning_max_swaps: parseInt(e.target.value) || 100,
                })
              }
              className="w-full text-sm bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-gray-200 focus:outline-none focus:border-blue-500"
              min={1}
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Max Layers
            </label>
            <input
              type="number"
              value={localSettings.pruning_max_layer}
              onChange={(e) =>
                setLocalSettings({
                  ...localSettings,
                  pruning_max_layer: parseInt(e.target.value) || 75,
                })
              }
              className="w-full text-sm bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-gray-200 focus:outline-none focus:border-blue-500"
              min={1}
              max={200}
            />
          </div>

          {error && (
            <div className="p-3 bg-red-900/30 rounded">
              <span className="text-xs text-red-400">{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-4 py-3 border-t border-gray-700">
          <button
            onClick={() => setPruningModalOpen(false)}
            className="px-3 py-1.5 text-xs text-gray-300 bg-gray-700 hover:bg-gray-600 rounded"
          >
            Close
          </button>
          <button
            onClick={handleSubmit}
            className="flex items-center gap-1 px-3 py-1.5 text-xs text-white bg-purple-600 hover:bg-purple-500 rounded"
            data-testid="pruning-start-btn"
          >
            <Play className="w-3 h-3" />
            Start Pruning
          </button>
        </div>
      </div>
    </div>
  )
}

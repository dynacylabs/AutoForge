import React from 'react'
import { useAppStore } from '../store/appStore'

export const StatusBar: React.FC = () => {
  const settings = useAppStore((s) => s.settings)
  const setSettings = useAppStore((s) => s.setSettings)
  const undo = useAppStore((s) => s.undo)
  const redo = useAppStore((s) => s.redo)
  const historyIndex = useAppStore((s) => s.historyIndex)
  const historyLength = useAppStore((s) => s.historyLength)

  // These bind directly to the same `settings` object the Settings modal
  // edits, so a change here or there is reflected in both immediately —
  // there is no separate "global params" copy to fall out of sync.
  const updateSetting = (key: keyof typeof settings, value: number) => {
    setSettings({ ...settings, [key]: value })
  }

  const layerHeight = settings.layer_height || 0.04
  const baseLayers = Math.round((settings.background_height || 0) / layerHeight)

  return (
    <div
      className="flex items-center gap-2 px-3 text-xs"
      style={{ height: 40, backgroundColor: 'var(--bg-toolbar)', borderTop: '1px solid var(--border)' }}
      data-testid="global-params"
    >
      <label style={{ color: 'var(--text-secondary)' }}>Layer Height</label>
      <input type="number" value={settings.layer_height} step={0.01} min={0.01} onChange={(e) => updateSetting('layer_height', parseFloat(e.target.value) || 0.01)} className="w-16 px-1 py-0.5 rounded text-xs text-center" style={{ backgroundColor: 'var(--bg-input)', border: '1px solid var(--border)' }} data-testid="global-layer-height" />

      <label style={{ color: 'var(--text-secondary)' }}>Background Height</label>
      <input type="number" value={settings.background_height} step={0.01} min={0} onChange={(e) => updateSetting('background_height', parseFloat(e.target.value) || 0)} className="w-16 px-1 py-0.5 rounded text-xs text-center" style={{ backgroundColor: 'var(--bg-input)', border: '1px solid var(--border)' }} data-testid="global-background-height" />

      <label style={{ color: 'var(--text-secondary)' }}>Base Layers</label>
      <input
        type="number"
        value={baseLayers}
        step={1}
        min={0}
        onChange={(e) => {
          const layers = Math.max(0, parseInt(e.target.value) || 0)
          updateSetting('background_height', parseFloat((layers * layerHeight).toFixed(4)))
        }}
        className="w-16 px-1 py-0.5 rounded text-xs text-center"
        style={{ backgroundColor: 'var(--bg-input)', border: '1px solid var(--border)' }}
        data-testid="global-base-layers"
      />

      <label style={{ color: 'var(--text-secondary)' }}>Dimension (mm)</label>
      <input type="number" value={settings.stl_output_size} step={1} min={10} onChange={(e) => updateSetting('stl_output_size', parseFloat(e.target.value) || 10)} className="w-16 px-1 py-0.5 rounded text-xs text-center" style={{ backgroundColor: 'var(--bg-input)', border: '1px solid var(--border)' }} data-testid="global-stl-size" />

      <div className="flex-1" />
      <div className="flex items-center gap-2 text-xs">
        <button
          onClick={() => undo()}
          disabled={historyIndex <= 0}
          className="px-2 py-0.5 rounded disabled:opacity-30"
          style={{ color: 'var(--green-accent)' }}
        >
          ↶ Undo
        </button>
        <button
          onClick={() => redo()}
          disabled={historyIndex >= historyLength - 1}
          className="px-2 py-0.5 rounded disabled:opacity-30"
          style={{ color: 'var(--border-light)' }}
        >
          ↷ Redo
        </button>
      </div>
    </div>
  )
}

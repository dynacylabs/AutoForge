import React, { useEffect } from 'react'
import { TopBar } from './components/TopBar'
import { FilamentLibrary } from './components/FilamentLibrary'
import { InputImagePanel } from './components/InputImagePanel'
import { Preview3DPanel } from './components/Preview3DPanel'
import { ColorCore } from './components/ColorCore'
import { ColorSliders } from './components/ColorSliders'
import { StatusBar } from './components/StatusBar'
import { SettingsModal } from './components/SettingsModal'
import { NewFilamentModal } from './components/NewFilamentModal'
import { ImportModal } from './components/ImportModal'
import { useAppStore } from './store/appStore'
import { useJobWebSocket } from './hooks/useJobWebSocket'

const App: React.FC = () => {
  const loadProjectState = useAppStore((s) => s.loadProjectState)
  const loadActiveFilaments = useAppStore((s) => s.loadActiveFilaments)
  const loadCurrentJob = useAppStore((s) => s.loadCurrentJob)
  const currentJob = useAppStore((s) => s.currentJob)
  const colorSliders = useAppStore((s) => s.colorSliders)
  const sliderLayerRange = useAppStore((s) => s.sliderLayerRange)
  const settings = useAppStore((s) => s.settings)

  const enabledDepths = colorSliders.filter((s) => s.enabled && s.layer > 0).map((s) => s.depth_mm)
  const currentMeshHeight = enabledDepths.length > 0 ? Math.max(...enabledDepths) : 0
  const totalMeshHeight = sliderLayerRange.max * (settings.layer_height || 0.04)

  // Connect to optimization WebSocket when a job is active
  const activeJobId = currentJob && ['pending', 'running', 'paused'].includes(currentJob.status)
    ? currentJob.job_id
    : null
  useJobWebSocket(activeJobId)

  useEffect(() => {
    const loadInitial = async () => {
      for (let attempt = 0; attempt < 20; attempt++) {
        try {
          await loadProjectState()
          await loadActiveFilaments()
          await loadCurrentJob()
          // If the responses succeeded, we're done
          break
        } catch {
          // Backend not ready yet – retry
          await new Promise(r => setTimeout(r, 1000))
        }
      }
    }
    loadInitial()
  }, [loadProjectState, loadActiveFilaments, loadCurrentJob])

  // Keyboard shortcuts for undo/redo
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'z') {
        e.preventDefault()
        useAppStore.getState().redo()
      } else if (e.ctrlKey && e.key === 'z') {
        e.preventDefault()
        useAppStore.getState().undo()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div data-testid="app" style={{ display: 'flex', flexDirection: 'column', width: '100vw', height: '100vh', backgroundColor: 'var(--bg-main)', color: 'var(--text-primary)' }}>
      <TopBar />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <aside style={{ width: 330, backgroundColor: 'var(--bg-sidebar)', borderRight: '1px solid var(--border)', overflow: 'hidden' }}>
          <FilamentLibrary />
        </aside>

        <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, display: 'flex', gap: 8, padding: 8, minHeight: 0 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <InputImagePanel />
            </div>
            <div style={{ width: 80, flexShrink: 0, display: 'flex' }}>
              <ColorCore />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <Preview3DPanel />
            </div>
          </div>

          <div style={{ textAlign: 'center', color: '#00ff55', fontSize: 18, fontWeight: 500, padding: '2px 0' }} data-testid="mesh-height-label">
            Mesh Height: {currentMeshHeight.toFixed(2)}/{totalMeshHeight.toFixed(2)}mm
          </div>

          <div style={{ height: 223, flexShrink: 0, minWidth: 0, overflow: 'hidden', borderTop: '1px solid var(--border)' }}>
            <ColorSliders />
          </div>
        </main>
      </div>

      <StatusBar />

      <SettingsModal />
      <NewFilamentModal />
      <ImportModal />
    </div>
  )
}

export default App

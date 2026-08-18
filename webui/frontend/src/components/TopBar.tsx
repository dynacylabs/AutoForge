import React, { useEffect, useRef, useState } from 'react'
import { useAppStore } from '../store/appStore'
import { Settings, Play, Pause, Square, Loader2, Scissors } from 'lucide-react'
import { PruningModal } from './PruningModal'
import { createProgressTracker, formatDuration, type ProgressTracker } from '../lib/progress'

export const TopBar: React.FC = () => {
  const setSettingsModalOpen = useAppStore((s) => s.setSettingsModalOpen)
  const currentJob = useAppStore((s) => s.currentJob)
  const startOptimization = useAppStore((s) => s.startOptimization)
  const pauseOptimization = useAppStore((s) => s.pauseOptimization)
  const resumeOptimization = useAppStore((s) => s.resumeOptimization)
  const cancelOptimization = useAppStore((s) => s.cancelOptimization)
  const setPruningModalOpen = useAppStore((s) => s.setPruningModalOpen)
  const pruningJob = useAppStore((s) => s.pruningJob)
  const pausePruning = useAppStore((s) => s.pausePruning)
  const resumePruning = useAppStore((s) => s.resumePruning)
  const cancelPruning = useAppStore((s) => s.cancelPruning)

  const trackerRef = useRef<ProgressTracker | null>(null)
  const [elapsedEta, setElapsedEta] = useState<{ elapsed: number; eta: number; stalled: boolean } | null>(null)

  const jobId = currentJob?.job_id
  const isActive = currentJob?.status === 'running' || currentJob?.status === 'paused'

  useEffect(() => {
    if (!isActive || !jobId) {
      trackerRef.current = null
      setElapsedEta(null)
      return
    }
    if (!trackerRef.current) trackerRef.current = createProgressTracker()
    const tick = () => {
      const tracker = trackerRef.current
      if (!tracker || !currentJob) return
      const state = tracker.update((currentJob.progress || 0) / 100, Date.now())
      setElapsedEta({ elapsed: state.elapsed, eta: state.eta, stalled: state.stalled })
    }
    tick()
    const interval = setInterval(tick, 1000)
    return () => clearInterval(interval)
  }, [isActive, jobId, currentJob])

  const handleStart = async () => {
    try {
      if (currentJob?.status === 'paused') {
        await resumeOptimization(currentJob.job_id)
      } else {
        await startOptimization()
      }
    } catch (e) {
      console.error('Failed to start:', e)
    }
  }

  const handlePause = async () => {
    if (currentJob?.status === 'running') {
      try {
        await pauseOptimization(currentJob.job_id)
      } catch (e) {
        console.error('Failed to pause:', e)
      }
    }
  }

  const handleCancel = async () => {
    if (currentJob) {
      await cancelOptimization(currentJob.job_id)
    }
  }

  const handlePrunePause = async () => {
    if (pruningJob?.status === 'running') {
      try {
        await pausePruning(pruningJob.job_id)
      } catch (e) {
        console.error('Failed to pause pruning:', e)
      }
    }
  }

  const handlePruneResume = async () => {
    if (pruningJob) {
      try {
        await resumePruning(pruningJob.job_id)
      } catch (e) {
        console.error('Failed to resume pruning:', e)
      }
    }
  }

  const handlePruneCancel = async () => {
    if (pruningJob) {
      await cancelPruning(pruningJob.job_id)
    }
  }

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-700" data-testid="top-bar">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-bold text-gray-100">AutoForge</h1>
        <span className="text-xs text-gray-500">v1.9.4</span>
      </div>

      <div className="flex items-center gap-2">
        {/* Progress indicator */}
        {(currentJob?.status === 'running' || currentJob?.status === 'paused') && (
          <div className="flex items-center gap-2 px-3 py-1 bg-gray-800 rounded">
            {currentJob.status === 'running' ? (
              <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
            ) : (
              <Pause className="w-3 h-3 text-yellow-400" />
            )}
            <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${currentJob.progress}%`,
                  backgroundColor: currentJob.status === 'paused' ? '#eab308' : '#60a5fa',
                }}
              />
            </div>
            <span className="text-xs text-gray-300">
              {currentJob.progress.toFixed(1)}%
            </span>
            <span className="text-xs text-gray-500" data-testid="job-iteration-count">
              ({currentJob.iteration}/{currentJob.total_iterations})
            </span>
            {currentJob.loss !== null && (
              <span className="text-xs text-gray-500">
                Loss: {currentJob.loss.toFixed(4)}
              </span>
            )}
            {currentJob.status === 'running' && elapsedEta && (
              <span className="text-xs text-gray-500" data-testid="job-elapsed-eta">
                {formatDuration(elapsedEta.elapsed)}
                {elapsedEta.stalled
                  ? ' · stalled'
                  : elapsedEta.eta > 0
                    ? ` · ETA ${formatDuration(elapsedEta.eta)}`
                    : ''}
              </span>
            )}
          </div>
        )}

        {currentJob?.status === 'completed' && (
          <div className="flex items-center gap-1 px-3 py-1 bg-green-900/30 rounded">
            <div className="w-2 h-2 rounded-full bg-green-400" />
            <span className="text-xs text-green-400">Done</span>
          </div>
        )}
        {currentJob?.status === 'failed' && (
          <div className="flex items-center gap-1 px-3 py-1 bg-red-900/30 rounded">
            <div className="w-2 h-2 rounded-full bg-red-400" />
            <span className="text-xs text-red-400">Failed{currentJob.error ? `: ${currentJob.error}` : ''}</span>
          </div>
        )}

        {(pruningJob?.status === 'running' || pruningJob?.status === 'pending' || pruningJob?.status === 'paused') && (
          <div className="flex items-center gap-2 px-3 py-1 bg-gray-800 rounded" data-testid="pruning-indicator">
            {pruningJob.status === 'paused' ? (
              <Pause className="w-3 h-3 text-yellow-400" />
            ) : (
              <Loader2 className="w-3 h-3 text-purple-400 animate-spin" />
            )}
            <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${pruningJob.progress}%`,
                  backgroundColor: pruningJob.status === 'paused' ? '#eab308' : '#a855f7',
                }}
              />
            </div>
            <span className="text-xs text-gray-300" data-testid="pruning-phase">
              {pruningJob.phase ? `${pruningJob.phase} ` : 'Pruning '}
              {pruningJob.progress.toFixed(1)}%
            </span>
            {pruningJob.status === 'running' ? (
              <button
                onClick={handlePrunePause}
                className="p-1 text-yellow-400 hover:text-yellow-300"
                title="Pause pruning"
                data-testid="prune-pause-btn"
              >
                <Pause className="w-3 h-3" />
              </button>
            ) : pruningJob.status === 'paused' ? (
              <button
                onClick={handlePruneResume}
                className="p-1 text-blue-400 hover:text-blue-300"
                title="Resume pruning"
                data-testid="prune-resume-btn"
              >
                <Play className="w-3 h-3" />
              </button>
            ) : null}
            <button
              onClick={handlePruneCancel}
              className="p-1 text-red-400 hover:text-red-300"
              title="Cancel pruning"
              data-testid="prune-cancel-btn"
            >
              <Square className="w-3 h-3" />
            </button>
          </div>
        )}
        {pruningJob?.status === 'completed' && (
          <div className="flex items-center gap-1 px-3 py-1 bg-purple-900/30 rounded" data-testid="pruning-done">
            <div className="w-2 h-2 rounded-full bg-purple-400" />
            <span className="text-xs text-purple-400">Pruned</span>
          </div>
        )}
        {pruningJob?.status === 'cancelled' && (
          <div className="flex items-center gap-1 px-3 py-1 bg-yellow-900/30 rounded" data-testid="pruning-cancelled">
            <div className="w-2 h-2 rounded-full bg-yellow-400" />
            <span className="text-xs text-yellow-400">Pruning cancelled (partial result kept)</span>
          </div>
        )}

        {currentJob?.status === 'running' ? (
          <button
            onClick={handlePause}
            className="flex items-center gap-1 px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 rounded text-xs text-white"
            data-testid="top-pause-btn"
          >
            <Pause className="w-3 h-3" />
            Pause
          </button>
        ) : currentJob?.status === 'paused' ? (
          <button
            onClick={handleStart}
            className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-xs text-white"
            data-testid="top-resume-btn"
          >
            <Play className="w-3 h-3" />
            Resume
          </button>
        ) : (
          <button
            onClick={handleStart}
            className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-xs text-white disabled:opacity-50"
            data-testid="top-start-btn"
          >
            <Play className="w-3 h-3" />
            Run
          </button>
        )}

        {(currentJob?.status === 'running' || currentJob?.status === 'paused') && (
          <button
            onClick={handleCancel}
            className="flex items-center gap-1 px-3 py-1.5 bg-red-600 hover:bg-red-500 rounded text-xs text-white"
            data-testid="top-cancel-btn"
          >
            <Square className="w-3 h-3" />
            Cancel
          </button>
        )}

        <button
          onClick={() => setPruningModalOpen(true)}
          className="flex items-center gap-1 px-3 py-1.5 bg-purple-600 hover:bg-purple-500 rounded text-xs text-white"
          data-testid="top-pruning-btn"
        >
          <Scissors className="w-3 h-3" />
          Pruning
        </button>

        <button
          onClick={() => setSettingsModalOpen(true)}
          className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-700 rounded"
          data-testid="settings-button"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>

      <PruningModal />
    </div>
  )
}

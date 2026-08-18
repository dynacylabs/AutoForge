import { create } from 'zustand'
import type { Filament, ColorSliderConfig, OptimizationSettings, JobStatus, ProjectState, PruningSettings, InitState, Snapshot } from '../types'

// Module-level undo stack — NOT in Zustand store to avoid infinite loops via subscribe
const UNDO_STACK: Snapshot[] = []
let UNDO_INDEX = -1

let pruningPollTimer: ReturnType<typeof setTimeout> | null = null

const defaultSliders: ColorSliderConfig[] = [
  { td: 2.0, layer: 8, depth_mm: 0.72, filament_uuid: '', enabled: true },
  { td: 3.0, layer: 13, depth_mm: 1.12, filament_uuid: '', enabled: true },
  { td: 8.0, layer: 20, depth_mm: 1.68, filament_uuid: '', enabled: true },
  { td: 5.0, layer: 27, depth_mm: 2.24, filament_uuid: '', enabled: true },
  ...Array.from({ length: 11 }, () => ({ td: 5.0, layer: 0, depth_mm: 0.0, filament_uuid: '', enabled: false })),
]

const defaultSettings: OptimizationSettings = {
  input_image: '',
  csv_file: '',
  json_file: '',
  output_folder: 'output',
  iterations: 6000,
  warmup_fraction: 1.0,
  learning_rate_warmup_fraction: 0.01,
  init_tau: 1.0,
  final_tau: 0.01,
  learning_rate: 0.015,
  layer_height: 0.04,
  max_layers: 75,
  min_layers: 0,
  background_height: 0.24,
  background_color: '#000000',
  auto_background_color: true,
  stl_output_size: 150,
  processing_reduction_factor: 2,
  nozzle_diameter: 0.4,
  early_stopping: 2000,
  perform_pruning: false,
  fast_pruning: true,
  fast_pruning_percent: 0.25,
  spike_removal: true,
  spike_threshold_layers: 1,
  pruning_max_colors: 100,
  pruning_max_swaps: 100,
  pruning_max_layer: 75,
  random_seed: 0,
  mps: false,
  run_name: null,
  tensorboard: false,
  num_init_rounds: 16,
  num_init_cluster_layers: -1,
  disable_visualization_for_gradio: 1,
  best_of: 1,
  discrete_check: 100,
  flatforge: false,
  cap_layers: 0,
  init_heightmap_method: 'kmeans',
  priority_mask: '',
  visualize: true,
}

const defaultPruningSettings: PruningSettings = {
  pruning_max_colors: 100,
  pruning_max_swaps: 100,
  pruning_max_layer: 75,
}

interface AppState {
  filaments: Filament[]
  filamentTypes: string[]
  filamentBrands: string[]
  activeFilaments: Filament[]
  colorSliders: ColorSliderConfig[]
  sliderLayerRange: { min: number; max: number }
  settings: OptimizationSettings
  currentJob: JobStatus | null
  inputImage: string | null
  previewImage: string | null
  previewVersion: number
  stlFile: string | null
  settingsModalOpen: boolean
  activeTab: string
  filterQuery: string
  filterType: string
  filterBrand: string
  pruningModalOpen: boolean
  pruningSettings: PruningSettings
  pruningJob: JobStatus | null
  initState: InitState
  hasRenderedInitPreview: boolean
  newFilamentModalOpen: boolean
  importModalOpen: boolean
  showDefaultLibrary: boolean
  customLibraryLoaded: boolean

  setFilaments: (filaments: Filament[]) => void
  setFilamentTypes: (types: string[]) => void
  setFilamentBrands: (brands: string[]) => void
  setActiveFilaments: (filaments: Filament[]) => void
  addActiveFilament: (filament: Filament) => void
  removeActiveFilament: (uuid: string) => void
  setSliders: (sliders: ColorSliderConfig[]) => void
  applySliders: (sliders: ColorSliderConfig[], range?: { min: number; max: number }) => void
  updateSlider: (index: number, updates: Partial<ColorSliderConfig>) => void
  setSettings: (settings: OptimizationSettings) => void
  setCurrentJob: (job: JobStatus | null) => void
  setInputImage: (image: string | null) => void
  setPreviewImage: (image: string | null) => void
  bumpPreviewVersion: () => void
  setStlFile: (file: string | null) => void
  setSettingsModalOpen: (open: boolean) => void
  setActiveTab: (tab: string) => void
  setFilterQuery: (query: string) => void
  setFilterType: (type: string) => void
  setFilterBrand: (brand: string) => void
  setPruningModalOpen: (open: boolean) => void
  setPruningSettings: (settings: PruningSettings) => void
  setPruningJob: (job: JobStatus | null) => void
  setInitState: (state: Partial<InitState>) => void
  setHasRenderedInitPreview: (val: boolean) => void
  setNewFilamentModalOpen: (open: boolean) => void
  setImportModalOpen: (open: boolean) => void
  setShowDefaultLibrary: (show: boolean) => void
  setCustomLibraryLoaded: (loaded: boolean) => void
  startOptimization: () => Promise<string>
  pauseOptimization: (jobId: string) => Promise<void>
  resumeOptimization: (jobId: string) => Promise<void>
  cancelOptimization: (jobId: string) => Promise<void>
  startPruning: () => Promise<string>
  pausePruning: (jobId: string) => Promise<void>
  resumePruning: (jobId: string) => Promise<void>
  cancelPruning: (jobId: string) => Promise<void>
  runInit: () => Promise<void>
  loadProjectState: () => Promise<void>
  loadActiveFilaments: () => Promise<void>

  // Undo/redo
  historyLength: number
  historyIndex: number
  undo: () => Promise<void>
  redo: () => Promise<void>
  captureSnapshot: () => void
}

export const useAppStore = create<AppState>((set, get) => ({
  filaments: [],
  filamentTypes: [],
  filamentBrands: [],
  activeFilaments: [],
  colorSliders: defaultSliders,
  sliderLayerRange: { min: 0, max: 75 },
  settings: defaultSettings,
  currentJob: null,
  inputImage: null,
  previewImage: null,
  previewVersion: 0,
  stlFile: null,
  settingsModalOpen: false,
  activeTab: 'PLA',
  filterQuery: '',
  filterType: '',
  filterBrand: '',
  pruningModalOpen: false,
  pruningSettings: defaultPruningSettings,
  pruningJob: null,
  initState: { status: 'idle', preview_image: null },
  hasRenderedInitPreview: false,
  newFilamentModalOpen: false,
  importModalOpen: false,
  showDefaultLibrary: false,
  customLibraryLoaded: false,
  historyLength: 0,
  historyIndex: -1,

  setFilaments: (filaments) => { set({ filaments }); queueCaptureSnapshot() },
  setFilamentTypes: (types) => set({ filamentTypes: types }),
  setFilamentBrands: (brands) => set({ filamentBrands: brands }),
  setActiveFilaments: (filaments) => { set({ activeFilaments: filaments }); queueCaptureSnapshot() },
  setSliders: (sliders) => { set({ colorSliders: sliders }); queueCaptureSnapshot() },
  applySliders: (sliders, range) => {
    set((state) => {
      // The optimizer/pruner can legitimately produce more or fewer bands
      // than any fixed column count — a material can recur in several
      // non-contiguous layer bands, and pruning changes the band count
      // further. Show exactly what it produced; padding to (or truncating
      // at) a fixed number here previously threw away real segments, which
      // then made the *next* render-with-sliders reconstruction (driven by
      // this same list) visibly wrong versus the true discrete solution.
      const merged = sliders.map((s, i) => ({ ...(state.colorSliders[i] ?? {}), ...s }))
      return {
        colorSliders: merged,
        ...(range && Number.isFinite(range.min) && Number.isFinite(range.max)
          ? { sliderLayerRange: { min: range.min, max: range.max } }
          : {}),
      }
    })
    queueCaptureSnapshot()
  },
  addActiveFilament: async (filament) => {
    set((state) => {
      const exists = state.activeFilaments.some((f) => f.uuid === filament.uuid)
      if (exists) return state
      return { activeFilaments: [...state.activeFilaments, filament] }
    })
    try {
      await fetch('/api/filaments/active', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(filament),
      })
    } catch (e) {
      console.error('Failed to add active filament:', e)
    }
    queueCaptureSnapshot()
  },
  removeActiveFilament: async (uuid) => {
    set((state) => ({
      activeFilaments: state.activeFilaments.filter((f) => f.uuid !== uuid),
    }))
    try {
      await fetch(`/api/filaments/active/${uuid}`, { method: 'DELETE' })
    } catch (e) {
      console.error('Failed to remove active filament:', e)
    }
    queueCaptureSnapshot()
  },

  updateSlider: (index, updates) => {
    set((state) => {
      const newSliders = [...state.colorSliders]
      newSliders[index] = { ...newSliders[index], ...updates }
      if (updates.td !== undefined || updates.layer !== undefined) {
        const lh = state.settings.layer_height || 0.04
        const layer = updates.layer !== undefined ? updates.layer : newSliders[index].layer
        newSliders[index].depth_mm = parseFloat((layer * lh).toFixed(2))
      }
      return { colorSliders: newSliders }
    })
    queueCaptureSnapshot()
  },

  setSettings: (settings) => {
    set({ settings })
    queueCaptureSnapshot()
  },
  setCurrentJob: (job) => {
    set({ currentJob: job });
    // When the job completes, mark the STL as available for the 3D preview
    if (job && job.status === 'completed') {
      set({ stlFile: job.job_id })
    }
    queueCaptureSnapshot()
  },
  setInputImage: (image) => { set({ inputImage: image }); queueCaptureSnapshot() },
  setPreviewImage: (image) => set({ previewImage: image }),
  bumpPreviewVersion: () => set((state) => ({ previewVersion: state.previewVersion + 1 })),
  setStlFile: (file) => set({ stlFile: file }),
  setSettingsModalOpen: (open) => set({ settingsModalOpen: open }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setFilterQuery: (query) => set({ filterQuery: query }),
  setFilterType: (type) => set({ filterType: type }),
  setFilterBrand: (brand) => set({ filterBrand: brand }),
  setPruningModalOpen: (open) => set({ pruningModalOpen: open }),
  setPruningSettings: (settings) => set({ pruningSettings: settings }),
  setPruningJob: (job) => set({ pruningJob: job }),
  setInitState: (state) => set((prev) => ({ initState: { ...prev.initState, ...state } })),
  setHasRenderedInitPreview: (val) => set({ hasRenderedInitPreview: val }),
  setNewFilamentModalOpen: (open) => set({ newFilamentModalOpen: open }),
  setImportModalOpen: (open) => set({ importModalOpen: open }),
  setShowDefaultLibrary: (show) => set({ showDefaultLibrary: show }),
  setCustomLibraryLoaded: (loaded) => set({ customLibraryLoaded: loaded }),

  loadActiveFilaments: async () => {
    try {
      const response = await fetch('/api/filaments/active')
      const data = await response.json()
      if (Array.isArray(data)) {
        set({ activeFilaments: data })
      }
    } catch {
      // Use empty list
    }
  },

  runInit: async () => {
    set({ initState: { status: 'initializing', preview_image: null } })
    try {
      const response = await fetch('/api/init/run', { method: 'POST' })
      if (!response.ok) {
        const err = await response.json()
        console.error('[store] Init rejected:', err.detail)
        set({ initState: { status: 'idle', preview_image: null } })
        return
      }
      const result = await response.json()
      set({ initState: { status: 'ready', preview_image: result.preview_image ?? null } })
    } catch (e) {
      console.error('[store] Failed to run init:', e)
      set({ initState: { status: 'idle', preview_image: null } })
    }
  },

  startOptimization: async () => {
    const state = get()
    const response = await fetch('/api/optimize/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.settings),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(err.detail ?? `HTTP ${response.status}`)
    }
    const data = await response.json()
    if (pruningPollTimer) clearTimeout(pruningPollTimer)
    set({ currentJob: { ...data, total_iterations: data.total_iterations || 0, progress: 0, iteration: 0, loss: null, error: null, started_at: new Date().toISOString(), completed_at: null, preview_image: null }, stlFile: null, pruningJob: null })
    return data.job_id
  },

  pauseOptimization: async (jobId) => {
    const response = await fetch(`/api/optimize/pause/${jobId}`, { method: 'POST' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    set((state) => ({
      currentJob: state.currentJob ? { ...state.currentJob, status: 'paused' } : null,
    }))
  },

  resumeOptimization: async (jobId) => {
    const response = await fetch(`/api/optimize/resume/${jobId}`, { method: 'POST' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    set((state) => ({
      currentJob: state.currentJob ? { ...state.currentJob, status: 'running' } : null,
    }))
  },

  cancelOptimization: async (jobId) => {
    const response = await fetch(`/api/optimize/cancel/${jobId}`, { method: 'POST' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    set((state) => ({
      currentJob: state.currentJob ? { ...state.currentJob, status: 'cancelled' } : null,
    }))
  },

  startPruning: async () => {
    const state = get()
    const response = await fetch('/api/pruning/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.pruningSettings),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(err.detail ?? `HTTP ${response.status}`)
    }
    const data = await response.json()
    set({ pruningJob: { ...data, progress: 0, iteration: 0, loss: null, error: null, started_at: new Date().toISOString(), completed_at: null, preview_image: null } })

    const jobId = data.job_id
    if (pruningPollTimer) clearTimeout(pruningPollTimer)
    const poll = async () => {
      try {
        const res = await fetch(`/api/optimize/status/${jobId}`)
        if (res.ok) {
          const job = await res.json()
          set({ pruningJob: job })
          if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') return
        }
      } catch {
        // Keep polling; backend may briefly be unavailable between prune stages
      }
      pruningPollTimer = setTimeout(poll, 1000)
    }
    poll()
    return data.job_id
  },

  pausePruning: async (jobId) => {
    const response = await fetch(`/api/optimize/pause/${jobId}`, { method: 'POST' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    set((state) => ({
      pruningJob: state.pruningJob ? { ...state.pruningJob, status: 'paused' } : null,
    }))
  },

  resumePruning: async (jobId) => {
    const response = await fetch(`/api/optimize/resume/${jobId}`, { method: 'POST' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    set((state) => ({
      pruningJob: state.pruningJob ? { ...state.pruningJob, status: 'running' } : null,
    }))
  },

  cancelPruning: async (jobId) => {
    const response = await fetch(`/api/optimize/cancel/${jobId}`, { method: 'POST' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    set((state) => ({
      pruningJob: state.pruningJob ? { ...state.pruningJob, status: 'cancelled' } : null,
    }))
  },

  loadProjectState: async () => {
    try {
      const response = await fetch('/api/project/state')
      const data = await response.json()
      // The backend now serialises this endpoint with plain (snake_case)
      // field names throughout — matching the frontend's ColorSliderConfig
      // type exactly, including nested fields like depth_mm and
      // filament_uuid — so this can be applied directly.
      if (data.color_sliders && data.color_sliders.length > 0) set({ colorSliders: data.color_sliders })
    } catch {
      // Use defaults
    }
  },

  captureSnapshot: () => {
    const state = get()
    const snapshot: Snapshot = {
      timestamp: Date.now() / 1000,
      label: 'State snapshot',
      activeFilaments: state.activeFilaments,
      colorSliders: state.colorSliders,
      settings: state.settings,
      inputImage: state.inputImage,
      currentJobId: state.currentJob?.job_id ?? null,
      optimizationResultId: state.currentJob?.status === 'completed' ? state.currentJob?.job_id : null,
    }

    fetch('/api/state/snapshot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(snapshot),
    }).catch(() => {})

    // Keep the on-reload project state fresh — GET /api/project/state is
    // read on every app mount, so if this never fires the endpoint keeps
    // serving whatever was last written (or nothing), and a stale/empty
    // snapshot silently overrides live defaults on next load.
    fetch('/api/project/state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        color_sliders: state.colorSliders,
        settings: state.settings,
        active_filaments: state.activeFilaments,
      }),
    }).catch(() => {})

    UNDO_STACK.push(snapshot)
    if (UNDO_STACK.length > 50) UNDO_STACK.shift()
    UNDO_INDEX = UNDO_STACK.length - 1
    set({ historyIndex: UNDO_INDEX, historyLength: UNDO_STACK.length })
  },

  undo: async () => {
    const state = get()
    if (state.historyIndex <= 0) return

    const targetIndex = state.historyIndex - 1
    const target = UNDO_STACK[targetIndex]
    if (!target) return

    // Stop running job
    if (state.currentJob) {
      try {
        await fetch(`/api/optimize/cancel/${state.currentJob.job_id}`, { method: 'POST' })
      } catch (_) {}
    }

    try {
      const resp = await fetch('/api/state/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timestamp: target.timestamp }),
      })
      if (resp.ok) {
        UNDO_INDEX = targetIndex
        set((prev) => ({
          activeFilaments: target.activeFilaments ?? prev.activeFilaments,
          colorSliders: target.colorSliders ?? prev.colorSliders,
          settings: target.settings ?? prev.settings,
          inputImage: target.inputImage ?? prev.inputImage,
          historyIndex: UNDO_INDEX,
          currentJob: null,
        }))
      }
    } catch (_) {}
  },

  redo: async () => {
    const state = get()
    const nextIndex = state.historyIndex + 1
    if (nextIndex >= UNDO_STACK.length) return

    const target = UNDO_STACK[nextIndex]
    if (!target) return

    if (state.currentJob) {
      try {
        await fetch(`/api/optimize/cancel/${state.currentJob.job_id}`, { method: 'POST' })
      } catch (_) {}
    }

    try {
      const resp = await fetch('/api/state/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timestamp: target.timestamp }),
      })
      if (resp.ok) {
        UNDO_INDEX = nextIndex
        set((prev) => ({
          activeFilaments: target.activeFilaments ?? prev.activeFilaments,
          colorSliders: target.colorSliders ?? prev.colorSliders,
          settings: target.settings ?? prev.settings,
          inputImage: target.inputImage ?? prev.inputImage,
          historyIndex: UNDO_INDEX,
          currentJob: null,
        }))
      }
    } catch (_) {}
  },
}))
// Debounced snapshot queue — safe from infinite loops because captureSnapshot
// only calls set({ historyIndex, historyLength }) which doesn't re-trigger this
let snapshotTimer: ReturnType<typeof setTimeout> | null = null

function queueCaptureSnapshot() {
  if (snapshotTimer) clearTimeout(snapshotTimer)
  snapshotTimer = setTimeout(() => {
    useAppStore.getState().captureSnapshot()
  }, 500)
}



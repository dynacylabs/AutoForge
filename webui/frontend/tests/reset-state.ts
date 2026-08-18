export const DEFAULT_SLIDERS = [
  { td: 2.0, layer: 8, depth_mm: 0.72, filament_uuid: '', enabled: true },
  { td: 3.0, layer: 13, depth_mm: 1.12, filament_uuid: '', enabled: true },
  { td: 8.0, layer: 20, depth_mm: 1.68, filament_uuid: '', enabled: true },
  { td: 5.0, layer: 27, depth_mm: 2.24, filament_uuid: '', enabled: true },
  ...Array.from({ length: 11 }, () => ({ td: 5.0, layer: 0, depth_mm: 0.0, filament_uuid: '', enabled: false })),
]

/** Reset server-side project state (color sliders / settings) to the
 * documented defaults. The backend persists this across reloads, so without
 * a reset, mutations from one test (or one run) bleed into the next.
 * `settings: {}` resolves to OptimizationSettings' own field defaults
 * (layer_height, background_height, stl_output_size, ...) via Pydantic. */
export async function resetProjectState(baseURL: string): Promise<void> {
  await fetch(`${baseURL}/api/project/state`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      color_sliders: DEFAULT_SLIDERS,
      settings: {},
      active_filaments: [],
    }),
  }).catch(() => {})
}

/** Remove filaments created by test runs so brand/tab lists and counts stay
 * deterministic across runs, and the (possibly real, shared) filament
 * library doesn't accumulate test data. Matches by substring rather than an
 * exact brand list — the suite uses several ad hoc test-only brand names
 * (E2E, E2ETest, TabTest, DeleteE2E, UpdateE2E, MarkTest, PersistTest,
 * TestBrand, ...) and new ones will keep appearing; every one of them
 * contains "test" or "e2e". */
export async function cleanupTestFilaments(baseURL: string): Promise<void> {
  const isTestBrand = (brand: string) => {
    const b = (brand || '').toLowerCase()
    return b.includes('test') || b.includes('e2e')
  }
  try {
    const res = await fetch(`${baseURL}/api/filaments`)
    if (res.ok) {
      const all = await res.json()
      for (const f of all) {
        if (isTestBrand(f.brand)) {
          await fetch(`${baseURL}/api/filaments/${f.uuid}`, { method: 'DELETE' }).catch(() => {})
          await fetch(`${baseURL}/api/filaments/active/${f.uuid}`, { method: 'DELETE' }).catch(() => {})
        }
      }
    }
  } catch {
    // Backend may not be reachable yet in some setups; tests will surface that.
  }
}

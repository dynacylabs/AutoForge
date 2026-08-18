import React, { useEffect, useState } from 'react'

interface HistoryResult {
  job_id: string
  status: string
  progress: number
  iteration: number
  started_at: string | null
  completed_at: string | null
}

export const ResultsHistory: React.FC<{ onSelect: (jobId: string) => void }> = ({ onSelect }) => {
  const [results, setResults] = useState<HistoryResult[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (open) {
      fetch('/api/optimize/history')
        .then((r) => r.json())
        .then(setResults)
        .catch(() => {})
    }
  }, [open])

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{ color: 'var(--cyan-accent)', fontSize: 10, border: '1px solid var(--border)', borderRadius: 4, padding: '2px 8px', backgroundColor: 'var(--bg-panel)', cursor: 'pointer' }}
      >
        Results
      </button>
    )
  }

  return (
    <div style={{ position: 'absolute', bottom: 44, right: 8, width: 300, backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 4, zIndex: 50, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 8px', borderBottom: '1px solid var(--border)', fontSize: 10, color: 'var(--text-secondary)' }}>
        <span>Results History</span>
        <button onClick={() => setOpen(false)} style={{ cursor: 'pointer', background: 'none', border: 'none', color: 'var(--text-secondary)' }}>X</button>
      </div>
      <div style={{ maxHeight: 200, overflowY: 'auto' }}>
        {results.map((r) => (
          <div
            key={r.job_id}
            onClick={() => { onSelect(r.job_id); setOpen(false) }}
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 8px', cursor: 'pointer', borderBottom: '1px solid var(--border)', fontSize: 9, color: 'var(--text-primary)' }}
          >
            <span>{r.job_id.slice(0, 8)}...</span>
            <span style={{ color: r.status === 'completed' ? 'var(--green-accent)' : 'var(--text-secondary)' }}>{r.status}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

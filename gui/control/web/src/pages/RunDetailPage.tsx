import React, { useEffect, useState } from 'react'
import { api } from '../api'
import type { JobInfo, RunDetail } from '../types'
import { OrbitCameraRunView } from '../workflows/orbit-camera/OrbitCameraRunView'
import { TurntableRunView } from '../workflows/turntable/TurntableRunView'

export function RunDetailPage({
  id,
  initialJobId,
  onBack,
  onJob,
}: {
  id: string
  initialJobId?: string
  onBack: () => void
  onJob: (runId: string, job: JobInfo) => void
}) {
  const [run, setRun] = useState<RunDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    api.run(id)
      .then((value) => { if (alive) { setRun(value); setError('') } })
      .catch((e) => { if (alive) setError(String(e)) })
    return () => { alive = false }
  }, [id])

  if (error) return <main className="page"><button className="back" onClick={onBack}>← Runs</button><div className="panel error-panel">{error}</div></main>
  if (!run) return <main className="page loading-page">Loading {id}…</main>

  const props = { id, initialJobId, onBack, onJob }
  return run.capture_mode === 'turntable'
    ? <TurntableRunView {...props} />
    : <OrbitCameraRunView {...props} />
}

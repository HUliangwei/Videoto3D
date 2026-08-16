import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { RunsPage } from './pages/RunsPage'
import { RunDetailPage } from './pages/RunDetailPage'
import { api } from './api'
import type { JobInfo } from './types'

function currentRun() { const match = location.hash.match(/^#\/runs\/([^/]+)$/); return match ? decodeURIComponent(match[1]) : null }

export default function App() {
  const [runId, setRunId] = useState<string | null>(currentRun())
  const [jobs, setJobs] = useState<Record<string,JobInfo>>({})
  const [stopping, setStopping] = useState(false)
  const [stopped, setStopped] = useState(false)
  const [exitError, setExitError] = useState('')
  useEffect(() => { const update = () => setRunId(currentRun()); addEventListener('hashchange', update); return () => removeEventListener('hashchange', update) }, [])
  const open = (id: string) => { location.hash = `/runs/${encodeURIComponent(id)}` }
  const back = () => { location.hash = '/' }
  const rememberJob = useCallback((id: string, job: JobInfo) => setJobs((old) => ({ ...old, [id]: job })), [])
  const activeJob = useMemo(() => Object.values(jobs).find((job) => job.status === 'running') ?? null, [jobs])
  const exitStudio = async () => {
    if (stopping) return; setStopping(true); setExitError('')
    try { await api.shutdown(); setStopped(true) }
    catch (e) { setExitError(String(e)); setStopping(false) }
  }
  if (stopped) return <div className="stopped-page"><div><span className="brand-dot" /><h1>Videoto3D Studio stopped.</h1><p>You can close this tab.</p></div></div>
  return <div className="app-shell"><div className="ambient ambient-a" /><div className="ambient ambient-b" /><nav className="topnav"><button className="brand" onClick={back}><span className="brand-dot" />Videoto3D</button><div className="nav-actions">{activeJob && <span className="global-job-status"><span className="global-job-pulse" />{activeJob.progress?.label || activeJob.kind}<b>{activeJob.progress?.detail || 'RUNNING'}</b></span>}<span className="version">Studio V1.2.0 · Artifact Inspector</span>{exitError && <span className="nav-error">{exitError}</span>}<button className="exit-studio" onClick={exitStudio} disabled={stopping}>{stopping ? 'Stopping…' : 'Exit Studio'}</button></div></nav>{runId ? <RunDetailPage id={runId} initialJobId={jobs[runId]?.job_id} onBack={back} onJob={rememberJob} /> : <RunsPage onOpen={open} onJob={rememberJob} />}<footer>Core is the single pipeline · Artifacts stay observable · Viewer stays reusable.</footer></div>
}

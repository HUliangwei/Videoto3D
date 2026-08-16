import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { JobInfo, ProgressStage } from '../types'

const terminal = new Set(['succeeded','failed','cancelled'])

function elapsedSeconds(job: JobInfo, now: number) {
  if (!job.started_at) return 0
  const start = Date.parse(job.started_at)
  const finish = job.finished_at ? Date.parse(job.finished_at) : now
  if (!Number.isFinite(start) || !Number.isFinite(finish)) return 0
  return Math.max(0, Math.floor((finish - start) / 1000))
}

function formatElapsed(seconds: number) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return h > 0 ? `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}` : `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
}

function StageItem({ stage }: { stage: ProgressStage }) {
  const symbol = stage.status === 'done' ? '✓' : stage.status === 'active' ? '●' : stage.status === 'error' ? '!' : stage.status === 'cancelled' ? '×' : '○'
  return <div className={`job-stage ${stage.status}`}><span className="job-stage-dot">{symbol}</span><span>{stage.label}</span></div>
}

export function JobPanel({ jobId, onTerminal, onUpdate }: { jobId: string; onTerminal: (job: JobInfo) => void; onUpdate?: (job: JobInfo) => void }) {
  const [job, setJob] = useState<JobInfo | null>(null)
  const [error, setError] = useState('')
  const [logOpen, setLogOpen] = useState(false)
  const [clock, setClock] = useState(Date.now())
  const logRef = useRef<HTMLPreElement>(null)

  useEffect(() => {
    let stopped = false
    const tick = async () => {
      try {
        const value = await api.job(jobId)
        if (stopped) return
        setJob(value); setError(''); onUpdate?.(value)
        if (value.status === 'failed') setLogOpen(true)
        if (terminal.has(value.status)) { onTerminal(value); return }
        setTimeout(tick, 700)
      } catch (e) {
        if (!stopped) { setError(String(e)); setTimeout(tick, 1200) }
      }
    }
    tick(); return () => { stopped = true }
  }, [jobId, onTerminal, onUpdate])

  useEffect(() => {
    if (!job || job.status !== 'running') return
    const timer = setInterval(() => setClock(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [job?.status, job?.started_at])

  useEffect(() => {
    if (logOpen && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [job?.lines?.length, logOpen])

  if (!job) return <section className="job-panel panel job-sticky">Connecting to job… {error}</section>
  const progress = job.progress
  const progressPercent = typeof progress?.percent === 'number' ? Math.max(0, Math.min(100, progress.percent)) : null
  const elapsed = formatElapsed(elapsedSeconds(job, clock))
  const statusLabel = job.status === 'running' ? 'RUNNING' : job.status.toUpperCase()

  return <section className={`job-panel panel job-sticky ${job.status}`}>
    <div className="job-head">
      <div>
        <div className="eyebrow">LIVE CORE JOB</div>
        <h3>{progress?.label || job.kind.toUpperCase()}</h3>
      </div>
      <div className="job-head-actions"><span className={`job-state ${job.status}`}>{statusLabel}</span>{job.status === 'running' && <button className="danger-button" onClick={() => api.cancelJob(jobId)}>Cancel Job</button>}</div>
    </div>

    <div className="job-progress-summary">
      <strong>{progress?.detail || job.status}</strong>
      <span>Elapsed&nbsp; {elapsed}</span>
    </div>

    {progressPercent !== null && <div className="progress-wrap" aria-label={`${progressPercent}%`}>
      <div className="progress-bar"><div className="progress-fill" style={{ width: `${progressPercent}%` }} /></div>
      <strong>{progressPercent.toFixed(progressPercent % 1 ? 1 : 0)}%</strong>
    </div>}

    {progress?.stages?.length ? <div className="job-stepper">{progress.stages.map((stage) => <StageItem key={stage.key} stage={stage} />)}</div> : null}

    {error && <div className="inline-error">{error}</div>}
    <button className="log-toggle" onClick={() => setLogOpen(!logOpen)}>{logOpen ? '▴' : '▾'} Live Log <span>{job.lines?.length || 0} lines</span></button>
    {logOpen && <pre ref={logRef}>{job.lines?.join('\n') || 'Waiting for output…'}</pre>}
  </section>
}

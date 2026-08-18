import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { AssetViewer } from '@videoto3d/viewer'
import { api } from '../../api'
import type { JobInfo, MeshSettings, RunDetail, SplatSettings } from '../../types'
import { ArtifactInspector } from '../../components/ArtifactInspector'
import { JobPanel } from '../../components/JobPanel'
import { PathInspector } from '../../components/PathInspector'
import { QualityPanel } from '../../components/QualityPanel'
import { RoiSelector } from '../../components/RoiSelector'
import { StatusPill } from '../../components/StatusPill'

const MESH: MeshSettings = {
  undistort_max_image_size: 2000,
  dense_resolution_level: 0,
  dense_number_views: 0,
  dense_max_threads: 0,
  refine_resolution_level: 1,
}

const SPLAT: SplatSettings = {
  steps: 30000,
  max_splats: 2000000,
  max_resolution: 1280,
  foreground_ratio: 0.6,
  min_foreground_observations: 2,
  cleanup_ratio: 0.7,
  cleanup_min_views: 3,
}

function metric(value: unknown, fallback = '—') {
  return value === undefined || value === null || value === '' ? fallback : String(value)
}

export function TurntableRunView({
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
  const [mode, setMode] = useState<'glb' | 'splat'>('glb')
  const [jobId, setJobId] = useState<string | undefined>(initialJobId)
  const [jobTerminal, setJobTerminal] = useState(false)

  const refresh = useCallback(async () => {
    try { setRun(await api.run(id)); setError('') } catch (e) { setError(String(e)) }
  }, [id])

  useEffect(() => {
    refresh()
    api.activeJob(id).then((job) => {
      if (job) { setJobId(job.job_id); setJobTerminal(false); onJob(id, job) }
    }).catch(() => {})
  }, [id])

  useEffect(() => {
    const timer = setInterval(() => refresh(), jobId ? 2200 : 6000)
    return () => clearInterval(timer)
  }, [refresh, jobId])

  const startJob = (job: JobInfo) => {
    setJobId(job.job_id)
    setJobTerminal(false)
    onJob(id, job)
  }
  const updateJob = useCallback((job: JobInfo) => onJob(id, job), [id, onJob])
  const onTerminal = useCallback((job: JobInfo) => {
    setJobTerminal(true)
    onJob(id, job)
    refresh()
  }, [id, onJob, refresh])

  const asset = useMemo(() => run?.assets?.[mode], [run, mode])
  useEffect(() => {
    if (!run) return
    if (mode === 'glb' && !run.assets.glb && run.assets.splat) setMode('splat')
    if (mode === 'splat' && !run.assets.splat && run.assets.glb) setMode('glb')
  }, [run, mode])

  if (error) return <main className="page"><button className="back" onClick={onBack}>← Runs</button><div className="panel error-panel">{error}</div></main>
  if (!run) return <main className="page loading-page">Loading {id}…</main>

  const extractReady = run.shared.extract?.status === 'ready'
  const maskReady = run.shared.mask?.status === 'ready'
  const sparseReady = run.shared.sparse?.status === 'ready'
  const meshReady = run.routes.mesh?.glb?.status === 'ready'
  const splatReady = run.routes.splat?.ply?.status === 'ready'
  const jobRunning = Boolean(jobId && !jobTerminal)
  const sparse = run.shared.sparse ?? {}
  const angleRatio = sparse.turntable_angle_valid_pair_ratio
  const angleText = typeof angleRatio === 'number' ? `${(angleRatio * 100).toFixed(1)}%` : '—'

  return <main className="page detail-page">
    <button className="back" onClick={onBack}>← All Runs</button>
    <header className="detail-head">
      <div>
        <div className="eyebrow">VIDEOTO3D V1.4 · TURNTABLE RESEARCH</div>
        <h1>{run.run_id}</h1>
        <p>{String(run.source?.original_input ?? run.source?.local_file ?? '')}</p>
        <p><strong>Capture:</strong> Turntable · camera fixed / rigid object rotates · RESEARCH</p>
      </div>
      <div className="status-row">
        <StatusPill value={sparseReady ? 'POSE BASELINE READY' : maskReady ? 'POSE PENDING' : extractReady ? 'MASK PENDING' : 'EXTRACTING'} />
        <StatusPill value={meshReady ? 'GEOMETRY COMPLETE' : 'GEOMETRY PENDING'} />
        <StatusPill value={splatReady ? 'GAUSSIAN COMPLETE' : 'GAUSSIAN PENDING'} />
      </div>
    </header>

    {jobId && <JobPanel jobId={jobId} onTerminal={onTerminal} onUpdate={updateJob} />}

    {extractReady && !maskReady && <section className="control-section">
      <div className="section-title">
        <div className="eyebrow">OBJECT OBSERVATION</div>
        <h2>Segment the rotating rigid object</h2>
      </div>
      <RoiSelector
        disabled={jobRunning}
        src={`/api/runs/${encodeURIComponent(id)}/frames/first`}
        onConfirm={async (box) => {
          try { startJob(await api.mask(id, box)) } catch (e) { setError(String(e)) }
        }}
      />
    </section>}

    {maskReady && <section className="control-section">
      <div className="section-title">
        <div className="eyebrow">TURNTABLE MOTION / POSE</div>
        <h2>Research pose baseline</h2>
        <p>V1.4 isolates the frozen V1.3 constrained-pose baseline here. Structured-essential, global-orbit and future SfM-free work can replace this module without touching Orbit Camera.</p>
      </div>
      <div className="control-grid">
        <article className="panel control-card">
          <div className="eyebrow">POSE BASELINE</div>
          <h3>{metric(sparse.pose_strategy, 'Not run')}</h3>
          <p>Run the isolated Turntable pose baseline and inspect trajectory quality before downstream reconstruction.</p>
          <button className="primary-button" disabled={jobRunning} onClick={async () => {
            try { startJob(await api.sparse(id)) } catch (e) { setError(String(e)) }
          }}>{sparseReady ? 'Run Pose Baseline Again' : 'Run Pose Baseline'}</button>
        </article>
        <article className="panel control-card">
          <div className="eyebrow">RESEARCH SIGNALS</div>
          <h3>Pose observability</h3>
          <p>Angle pairs: <strong>{angleText}</strong></p>
          <p>Direction: <strong>{metric(sparse.turntable_direction)}</strong></p>
          <p>Sparse points: <strong>{metric(sparse.points3D)}</strong></p>
          <p>Track length: <strong>{metric(sparse.mean_track_length)}</strong></p>
          <p>Reprojection: <strong>{metric(sparse.mean_reprojection_error)}</strong></p>
        </article>
      </div>
    </section>}

    {sparseReady && <section className="control-section">
      <div className="section-title">
        <div className="eyebrow">RECONSTRUCTION</div>
        <h2>Independent downstream experiments</h2>
      </div>
      <div className="control-grid">
        <article className="panel control-card">
          <div className="eyebrow">GEOMETRY</div>
          <h3>Known poses → OpenMVS → GLB</h3>
          <button className="primary-button" disabled={jobRunning} onClick={async () => {
            try { startJob(await api.routeMesh(id, MESH)) } catch (e) { setError(String(e)) }
          }}>{meshReady ? 'Run Geometry Again' : 'Run Geometry'}</button>
        </article>
        <article className="panel control-card splat-control">
          <div className="eyebrow">GAUSSIAN</div>
          <h3>Current Brush baseline → PLY</h3>
          <p>Future RotGS-like SfM-free work remains isolated inside the Turntable workflow.</p>
          <button className="primary-button" disabled={jobRunning} onClick={async () => {
            try { startJob(await api.routeSplat(id, SPLAT)) } catch (e) { setError(String(e)) }
          }}>{splatReady ? 'Run Gaussian Again' : 'Run Gaussian'}</button>
        </article>
      </div>
    </section>}

    <ArtifactInspector runId={id} refreshKey={run.updated_at ?? ''} />

    <section className="viewer-section">
      <div className="viewer-topbar">
        <div><div className="eyebrow">RESULT VIEWER</div><h2>{mode === 'glb' ? 'Geometry / GLB' : 'Gaussian / PLY'}</h2></div>
        <div className="segmented">
          <button className={mode === 'glb' ? 'selected' : ''} disabled={!run.assets.glb} onClick={() => setMode('glb')}>Geometry</button>
          <button className={mode === 'splat' ? 'selected' : ''} disabled={!run.assets.splat} onClick={() => setMode('splat')}>Gaussian</button>
        </div>
      </div>
      <div className="viewer-frame">
        {asset ? <AssetViewer type={mode} src={asset} /> : <div className="viewer-empty">当前研究路线尚无可预览资产。</div>}
        <div className="viewer-caption"><span>{run.run_id}</span><span>{mode === 'glb' ? 'GLB · Turntable geometry' : 'PLY · Turntable Gaussian'}</span></div>
      </div>
    </section>

    <section className="quality-section">
      <div className="section-title"><div className="eyebrow">QUALITY</div><h2>Research reconstruction report</h2></div>
      <QualityPanel report={run.quality} />
    </section>
    <PathInspector paths={run.paths} />
  </main>
}

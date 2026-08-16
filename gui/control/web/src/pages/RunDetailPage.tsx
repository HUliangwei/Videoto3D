import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { AssetViewer } from '@videoto3d/viewer'
import { api } from '../api'
import type { JobInfo, MeshSettings, RunDetail, SplatSettings } from '../types'
import { QualityPanel } from '../components/QualityPanel'
import { StatusPill } from '../components/StatusPill'
import { RoiSelector } from '../components/RoiSelector'
import { JobPanel } from '../components/JobPanel'
import { PathInspector } from '../components/PathInspector'
import { ArtifactInspector } from '../components/ArtifactInspector'

const DEFAULT_MESH: MeshSettings = {
  undistort_max_image_size: 2000,
  dense_resolution_level: 0,
  dense_number_views: 0,
  dense_max_threads: 0,
  refine_resolution_level: 1,
}

const DEFAULT_SPLAT: SplatSettings = {
  steps: 30000,
  max_splats: 2000000,
  max_resolution: 1280,
  foreground_ratio: 0.6,
  min_foreground_observations: 2,
  cleanup_ratio: 0.7,
  cleanup_min_views: 3,
}

function NumberField({ label, value, step = 1, onChange }: { label: string; value: number; step?: number; onChange: (value: number) => void }) {
  return <label className="mini-field"><span>{label}</span><input type="number" value={value} step={step} onChange={(e) => onChange(Number(e.target.value))} /></label>
}

export function RunDetailPage({ id, initialJobId, onBack, onJob }: { id: string; initialJobId?: string; onBack: () => void; onJob: (runId: string, job: JobInfo) => void }) {
  const [run, setRun] = useState<RunDetail | null>(null)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'glb' | 'splat'>('glb')
  const [jobId, setJobId] = useState<string | undefined>(initialJobId)
  const [jobTerminal, setJobTerminal] = useState(false)
  const [meshSettings, setMeshSettings] = useState<MeshSettings>(DEFAULT_MESH)
  const [splatSettings, setSplatSettings] = useState<SplatSettings>(DEFAULT_SPLAT)
  const [meshAdvanced, setMeshAdvanced] = useState(false)
  const [splatAdvanced, setSplatAdvanced] = useState(false)
  const [meshHydrated, setMeshHydrated] = useState(false)

  const refresh = useCallback(async () => {
    try { setRun(await api.run(id)); setError('') } catch (e) { setError(String(e)) }
  }, [id])
  useEffect(() => { refresh(); api.activeJob(id).then((job) => { if (job) { setJobId(job.job_id); setJobTerminal(false); onJob(id, job) } }).catch(() => {}) }, [id])
  useEffect(() => { setMeshHydrated(false); setMeshSettings(DEFAULT_MESH) }, [id])
  useEffect(() => { const timer = setInterval(() => refresh(), jobId ? 2200 : 6000); return () => clearInterval(timer) }, [refresh, jobId])
  useEffect(() => {
    if (!run || meshHydrated) return
    const profile = run.routes.mesh?.texture?.profile
    if (profile) setMeshSettings({ ...DEFAULT_MESH, ...profile })
    setMeshHydrated(true)
  }, [run, meshHydrated])

  const startJob = (job: JobInfo) => { setJobId(job.job_id); setJobTerminal(false); onJob(id, job) }
  const updateJob = useCallback((job: JobInfo) => onJob(id, job), [id, onJob])
  const onTerminal = useCallback((job: JobInfo) => { setJobTerminal(true); onJob(id, job); refresh() }, [id, onJob, refresh])
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
  const sharedReady = extractReady && maskReady && sparseReady
  const meshReady = run.routes.mesh?.glb?.status === 'ready'
  const splatReady = run.routes.splat?.ply?.status === 'ready'
  const jobRunning = Boolean(jobId && !jobTerminal)

  return <main className="page detail-page">
    <button className="back" onClick={onBack}>← All Runs</button>
    <header className="detail-head"><div><div className="eyebrow">VIDEOTO3D RUN</div><h1>{run.run_id}</h1><p>{String(run.source?.original_input ?? run.source?.local_file ?? '')}</p></div><div className="status-row"><StatusPill value={sharedReady ? 'SHARED READY' : maskReady ? 'SPARSE PENDING' : extractReady ? 'MASK PENDING' : 'EXTRACTING'} /><StatusPill value={meshReady ? 'MESH COMPLETE' : 'MESH PENDING'} /><StatusPill value={splatReady ? 'SPLAT COMPLETE' : 'SPLAT PENDING'} /></div></header>

    {jobId && <JobPanel jobId={jobId} onTerminal={onTerminal} onUpdate={updateJob} />}

    {extractReady && !maskReady && <section className="control-section"><div className="section-title"><div className="eyebrow">SHARED · OBJECT SELECTION</div><h2>Choose the reconstruction subject</h2></div><RoiSelector disabled={jobRunning} src={`/api/runs/${encodeURIComponent(id)}/frames/first`} onConfirm={async (box) => { try { startJob(await api.mask(id, box)) } catch (e) { setError(String(e)) } }} /></section>}

    {maskReady && <section className="control-section"><div className="section-title"><div className="eyebrow">ROUTE CONTROL</div><h2>Build one route or both.</h2></div><div className="control-grid">
      <article className="panel control-card"><div className="eyebrow">MESH ROUTE</div><h3>OpenMVS → textured GLB</h3><p>自动复用 Shared frames / masks / COLMAP；参数变化只从受影响的最早 Mesh 阶段往后重跑。</p><button className="text-button" onClick={() => setMeshAdvanced(!meshAdvanced)}>{meshAdvanced ? 'Hide Settings' : 'Mesh Settings'}</button>
        {meshAdvanced && <div className="mesh-settings-wrap"><div className="splat-fields"><NumberField label="Undistort max size" value={meshSettings.undistort_max_image_size} onChange={(v) => setMeshSettings({...meshSettings, undistort_max_image_size:v})} /><NumberField label="Dense resolution level" value={meshSettings.dense_resolution_level} onChange={(v) => setMeshSettings({...meshSettings, dense_resolution_level:v})} /><NumberField label="Dense views (0=Auto)" value={meshSettings.dense_number_views} onChange={(v) => setMeshSettings({...meshSettings, dense_number_views:v})} /><NumberField label="Dense threads (0=Auto)" value={meshSettings.dense_max_threads} onChange={(v) => setMeshSettings({...meshSettings, dense_max_threads:v})} /><NumberField label="Refine resolution level" value={meshSettings.refine_resolution_level} onChange={(v) => setMeshSettings({...meshSettings, refine_resolution_level:v})} /></div><div className="locked-setting"><strong>Texture workaround · locked</strong><span>Seam leveling: OFF · Mask label: 0 · BUG-0001</span></div></div>}
        <button className="primary-button" disabled={jobRunning} onClick={async () => { try { startJob(await api.routeMesh(id, meshSettings)) } catch (e) { setError(String(e)) } }}>{meshReady ? 'Run Mesh Again' : 'Run Mesh'}</button></article>
      <article className="panel control-card splat-control"><div className="eyebrow">SPLAT ROUTE</div><h3>Brush → Cleanup → PLY</h3><p>默认 30k / 2M / 1280；训练参数变化才重训，Cleanup 参数变化可只重跑清理。</p><button className="text-button" onClick={() => setSplatAdvanced(!splatAdvanced)}>{splatAdvanced ? 'Hide Settings' : 'Splat Settings'}</button>
        {splatAdvanced && <div className="splat-fields"><NumberField label="Steps" value={splatSettings.steps} onChange={(v) => setSplatSettings({...splatSettings, steps:v})} /><NumberField label="Max splats" value={splatSettings.max_splats} onChange={(v) => setSplatSettings({...splatSettings, max_splats:v})} /><NumberField label="Resolution" value={splatSettings.max_resolution} onChange={(v) => setSplatSettings({...splatSettings, max_resolution:v})} /><NumberField label="FG ratio" value={splatSettings.foreground_ratio} step={0.05} onChange={(v) => setSplatSettings({...splatSettings, foreground_ratio:v})} /><NumberField label="Min FG views" value={splatSettings.min_foreground_observations} onChange={(v) => setSplatSettings({...splatSettings, min_foreground_observations:v})} /><NumberField label="Cleanup ratio" value={splatSettings.cleanup_ratio} step={0.05} onChange={(v) => setSplatSettings({...splatSettings, cleanup_ratio:v})} /><NumberField label="Cleanup views" value={splatSettings.cleanup_min_views} onChange={(v) => setSplatSettings({...splatSettings, cleanup_min_views:v})} /></div>}
        <button className="primary-button" disabled={jobRunning} onClick={async () => { try { startJob(await api.routeSplat(id, splatSettings)) } catch (e) { setError(String(e)) } }}>{splatReady ? 'Run Splat Again' : 'Run Splat'}</button>
      </article>
    </div></section>}

    <ArtifactInspector runId={id} refreshKey={run.updated_at ?? ''} />

    <section className="viewer-section"><div className="viewer-topbar"><div><div className="eyebrow">RESULT VIEWER</div><h2>{mode === 'glb' ? 'Mesh / GLB' : 'Gaussian Splat / PLY'}</h2></div><div className="segmented"><button className={mode === 'glb' ? 'selected' : ''} disabled={!run.assets.glb} onClick={() => setMode('glb')}>Mesh</button><button className={mode === 'splat' ? 'selected' : ''} disabled={!run.assets.splat} onClick={() => setMode('splat')}>Splat</button></div></div><div className="viewer-frame">{asset ? <AssetViewer type={mode} src={asset} /> : <div className="viewer-empty">当前 Route 尚无可预览资产。</div>}<div className="viewer-caption"><span>{run.run_id}</span><span>{mode === 'glb' ? 'GLB · textured mesh' : 'PLY · cleaned Gaussian splat'}</span></div></div></section>

    <section className="quality-section"><div className="section-title"><div className="eyebrow">QUALITY</div><h2>Reconstruction report</h2></div><QualityPanel report={run.quality} /></section>
    <PathInspector paths={run.paths} />
  </main>
}

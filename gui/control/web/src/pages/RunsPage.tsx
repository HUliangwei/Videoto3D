import React, { useEffect, useState } from 'react'
import { api } from '../api'
import type { JobInfo, RunSummary } from '../types'
import { RouteCard } from '../components/RouteCard'
import { NewRunPanel } from '../components/NewRunPanel'

export function RunsPage({ onOpen, onJob }: { onOpen: (id: string) => void; onJob: (runId: string, job: JobInfo) => void }) {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  useEffect(() => { api.runs().then(setRuns).catch((e) => setError(String(e))) }, [])
  return <main className="page runs-page">
    <section className="hero-copy hero-with-action"><div><div className="eyebrow">LOCAL 3D RECONSTRUCTION STUDIO</div><h1>Video to two forms of 3D.</h1><p>创建 Run 时按采集方式选择 Orbit Camera 或 Turntable；两条工作流共享 Run 管理，但从重建逻辑到网页交互相互隔离。</p></div><button className="primary-button hero-button" onClick={() => setCreating(true)}>+ New Run</button></section>
    {error && <div className="panel error-panel">{error}</div>}
    {!error && runs.length === 0 && <div className="panel empty-panel">暂无 Run。点击 New Run 导入一个视频。</div>}
    <section className="run-grid">{runs.map((run) => <button className="run-card" key={run.run_id} onClick={() => onOpen(run.run_id)}><div className="run-card-head"><div><div className="eyebrow">RUN</div><h2>{run.run_id}</h2></div><span className="open-mark">↗</span></div><div className="route-stack"><RouteCard title={run.capture_mode === 'turntable' ? 'Turntable' : 'Orbit Camera'} subtitle={`${run.frames} frames · ${run.capture_mode === 'turntable' ? 'Research' : 'Stable'}`} status={run.shared_status} accent="shared" /><RouteCard title="Mesh Route" subtitle="OpenMVS · GLB" status={run.mesh_status} accent="mesh" /><RouteCard title="Splat Route" subtitle="Brush · PLY" status={run.splat_status} accent="splat" /></div></button>)}</section>
    {creating && <NewRunPanel onClose={() => setCreating(false)} onCreated={(id, job) => { onJob(id, job); onOpen(id) }} />}
  </main>
}

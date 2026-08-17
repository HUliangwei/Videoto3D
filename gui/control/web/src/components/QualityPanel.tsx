import React from 'react'

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="metric"><span>{label}</span><strong>{value ?? '—'}</strong></div>
}
function pct(value: unknown) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}
function num(value: unknown) {
  return typeof value === 'number' ? value.toLocaleString() : '—'
}

export function QualityPanel({ report }: { report: any | null }) {
  if (!report) return <div className="panel empty-panel">Quality report 尚未生成。</div>
  const shared = report.shared ?? {}
  const mesh = report.mesh_route ?? {}
  const splat = report.splat_route ?? {}
  return (
    <div className="quality-grid">
      <section className="panel"><div className="eyebrow">SHARED</div><h3>Capture & SfM</h3>
        <Metric label="Capture Mode" value={shared.capture_mode === 'turntable' ? 'TURNTABLE' : 'ORBIT CAMERA'} />
        <Metric label="Sparse Strategy" value={shared.sparse_mask_guided ? 'MASK-GUIDED' : 'FULL RGB'} />
        <Metric label="Frames" value={num(shared.frames)} />
        <Metric label="SAM2 Masks" value={num(shared.masks)} />
        <Metric label="COLMAP Registration" value={pct(shared.registration_rate)} />
        <Metric label="Sparse Points" value={num(shared.sparse_points)} />
      </section>
      <section className="panel"><div className="eyebrow">MESH ROUTE</div><h3>OpenMVS → GLB</h3>
        <Metric label="Dense Points" value={num(mesh.dense_points)} />
        <Metric label="Vertices" value={num(mesh.final_vertices)} />
        <Metric label="Faces" value={num(mesh.final_faces)} />
        <Metric label="Status" value={mesh.status?.toUpperCase?.() ?? '—'} />
      </section>
      <section className="panel"><div className="eyebrow">SPLAT ROUTE</div><h3>Brush → Cleanup</h3>
        <Metric label="Training Steps" value={num(splat.training_steps)} />
        <Metric label="Raw Splats" value={num(splat.raw_splats)} />
        <Metric label="Clean Splats" value={num(splat.clean_splats)} />
        <Metric label="Removed" value={pct(splat.removal_ratio)} />
      </section>
    </div>
  )
}

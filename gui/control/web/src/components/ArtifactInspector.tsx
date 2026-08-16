import React, { useEffect, useMemo, useState } from 'react'
import { AssetViewer, type AssetType } from '@videoto3d/viewer'
import { api } from '../api'
import type { ArtifactCatalog, ArtifactItem } from '../types'
import './artifact-inspector.css'

function stateLabel(state: ArtifactItem['state']) {
  if (state === 'ready') return 'READY'
  if (state === 'partial') return 'PARTIAL'
  if (state === 'missing') return 'MISSING'
  return 'PENDING'
}

function canOpen(item: ArtifactItem) {
  return item.state === 'ready' || item.state === 'partial'
}

function metricLabel(key: string) {
  const labels: Record<string,string> = {
    count: 'items', masks: 'masks', frames: 'frames', points: 'points', vertices: 'verts', faces: 'faces', size: 'size',
  }
  return labels[key] ?? key.replace(/_/g, ' ')
}

function viewerType(item: ArtifactItem): AssetType | null {
  if (item.kind === 'pointcloud' || item.kind === 'mesh-ply' || item.kind === 'glb' || item.kind === 'splat') return item.kind
  return null
}

function SequencePreview({ item }: { item: ArtifactItem }) {
  const [index, setIndex] = useState(0)
  const [mode, setMode] = useState<'original'|'mask'|'overlay'>('overlay')
  const count = Math.max(0, item.count ?? 0)
  useEffect(() => { setIndex(0); setMode(item.kind === 'mask-sequence' ? 'overlay' : 'original') }, [item.key])
  const safeIndex = Math.min(index, Math.max(count - 1, 0))
  const frame = item.frame_base_url ? `${item.frame_base_url}/${safeIndex}` : ''
  const mask = item.mask_base_url ? `${item.mask_base_url}/${safeIndex}` : ''
  const image = item.image_base_url ? `${item.image_base_url}/${safeIndex}` : frame

  return <div className="artifact-sequence">
    <div className="artifact-image-stage">
      {item.kind === 'mask-sequence' ? <>
        {mode === 'original' && <img src={frame} alt={`${item.label} original ${safeIndex + 1}`} />}
        {mode === 'mask' && <img src={mask} alt={`${item.label} mask ${safeIndex + 1}`} />}
        {mode === 'overlay' && <div className="artifact-mask-stack"><img src={frame} alt="Original frame" /><img className="mask-layer" src={mask} alt="SAM2 mask overlay" /></div>}
      </> : <img src={image} alt={`${item.label} ${safeIndex + 1}`} />}
    </div>
    <div className="artifact-sequence-controls">
      {item.kind === 'mask-sequence' && <div className="artifact-mode-tabs">
        {(['original','mask','overlay'] as const).map((value) => <button key={value} className={mode === value ? 'selected' : ''} onClick={() => setMode(value)}>{value === 'original' ? 'Original' : value === 'mask' ? 'Mask' : 'Overlay'}</button>)}
      </div>}
      <button className="artifact-open" disabled={safeIndex <= 0} onClick={() => setIndex((v) => Math.max(0, v - 1))}>←</button>
      <input aria-label="Artifact frame" type="range" min={0} max={Math.max(count - 1, 0)} value={safeIndex} onChange={(e) => setIndex(Number(e.target.value))} />
      <button className="artifact-open" disabled={safeIndex >= count - 1} onClick={() => setIndex((v) => Math.min(count - 1, v + 1))}>→</button>
      <span className="artifact-index">{count ? safeIndex + 1 : 0} / {count}</span>
    </div>
  </div>
}

function SinglePreview({ item }: { item: ArtifactItem }) {
  if (item.kind === 'image-sequence' || item.kind === 'mask-sequence') return <SequencePreview item={item} />
  const type = viewerType(item)
  if (type && item.asset_url) return <AssetViewer type={type} src={item.asset_url} className="artifact-3d" />
  return <div className="viewer-empty">No preview is available for this artifact.</div>
}

function ComparePreview({ left, right }: { left: ArtifactItem; right: ArtifactItem }) {
  const leftType = viewerType(left)
  const rightType = viewerType(right)
  if (!leftType || !rightType || !left.asset_url || !right.asset_url) return <div className="viewer-empty">Comparison is unavailable.</div>
  return <div className="artifact-compare-grid">
    <div className="artifact-compare-pane"><span className="artifact-compare-label">{left.label}</span><AssetViewer type={leftType} src={left.asset_url} className="artifact-3d" /></div>
    <div className="artifact-compare-pane"><span className="artifact-compare-label">{right.label}</span><AssetViewer type={rightType} src={right.asset_url} className="artifact-3d" /></div>
  </div>
}

export function ArtifactInspector({ runId, refreshKey = '' }: { runId: string; refreshKey?: string }) {
  const [catalog, setCatalog] = useState<ArtifactCatalog | null>(null)
  const [selected, setSelected] = useState<ArtifactItem | null>(null)
  const [compare, setCompare] = useState<[ArtifactItem, ArtifactItem] | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try { setCatalog(await api.artifacts(runId)); setError('') }
    catch (e) { setError(String(e)) }
    finally { setLoading(false) }
  }
  useEffect(() => { refresh() }, [runId, refreshKey])

  const items = useMemo(() => catalog?.groups.flatMap((group) => group.artifacts) ?? [], [catalog])
  const byKey = useMemo(() => Object.fromEntries(items.map((item) => [item.key, item])) as Record<string,ArtifactItem>, [items])
  const comparePairs = [
    ['raw-mesh','refined-mesh','Raw Mesh ↔ Refined Mesh'],
    ['raw-splat','clean-splat','Raw Splat ↔ Clean Splat'],
  ] as const

  return <section className="artifact-section">
    <div className="artifact-intro"><div><div className="eyebrow">PIPELINE ARTIFACTS</div><h2>Intermediate Results</h2><p>每一步完成后直接查看真实中间产物。先判断哪一步开始偏离，再决定是否调参数；这些画面也可以直接作为 README Workflow Demo 的素材。</p></div><button className="artifact-refresh" onClick={refresh} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh Artifacts'}</button></div>
    {error && <div className="artifact-error">{error}</div>}
    {catalog?.groups.map((group) => <div className="artifact-group" key={group.key}>
      <div className="artifact-group-head"><h3>{group.label}</h3><span className="artifact-group-line" /></div>
      <div className="artifact-grid">{group.artifacts.map((item) => <article key={item.key} className={`artifact-card ${item.state}`}>
        <div className="artifact-card-top"><div><div className="artifact-stage">{item.stage}</div><h4>{item.label}</h4></div><span className={`artifact-state ${item.state}`}>{stateLabel(item.state)}</span></div>
        <p>{item.description}</p>
        <div className="artifact-metrics">{Object.entries(item.metrics).filter(([key]) => key !== 'size_bytes').map(([key,value]) => <span className="artifact-metric" key={key}>{metricLabel(key)} · {String(value)}</span>)}</div>
        <button className="artifact-open" disabled={!canOpen(item)} onClick={() => { setCompare(null); setSelected(item) }}>{canOpen(item) ? 'View Artifact' : item.state === 'missing' ? 'File Missing' : 'Not Ready'}</button>
      </article>)}</div>
      <div className="artifact-compare-row">{comparePairs.map(([a,b,label]) => {
        const left = byKey[a]; const right = byKey[b]
        if (!left || !right || group.artifacts.every((item) => item.key !== a && item.key !== b)) return null
        return <button key={label} className="artifact-compare" disabled={!canOpen(left) || !canOpen(right)} onClick={() => { setSelected(null); setCompare([left,right]) }}>Compare · {label}</button>
      })}</div>
    </div>)}
    {(selected || compare) && <div className="artifact-modal-backdrop" role="dialog" aria-modal="true" onMouseDown={(e) => { if (e.target === e.currentTarget) { setSelected(null); setCompare(null) } }}>
      <div className="artifact-modal"><div className="artifact-modal-head"><div><div className="eyebrow">ARTIFACT PREVIEW</div><h3>{compare ? `${compare[0].label} ↔ ${compare[1].label}` : selected?.label}</h3></div><button className="artifact-close" onClick={() => { setSelected(null); setCompare(null) }}>×</button></div><div className="artifact-modal-body">{compare ? <ComparePreview left={compare[0]} right={compare[1]} /> : selected ? <SinglePreview item={selected} /> : null}</div></div>
    </div>}
  </section>
}

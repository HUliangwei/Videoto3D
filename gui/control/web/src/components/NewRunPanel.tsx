import React, { useMemo, useState } from 'react'
import { api } from '../api'
import type { JobInfo } from '../types'

function suggestedId(file: File | null) {
  if (!file) return ''
  return file.name.replace(/\.[^.]+$/, '').replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^[^A-Za-z0-9]+/, '').slice(0, 64) || 'run_001'
}

export function NewRunPanel({ onClose, onCreated }: { onClose: () => void; onCreated: (runId: string, job: JobInfo) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [runId, setRunId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const hint = useMemo(() => suggestedId(file), [file])
  const submit = async () => {
    if (!file) return setError('请选择视频文件。')
    const id = (runId || hint).trim()
    if (!id) return setError('请输入 Run ID。')
    setBusy(true); setError('')
    try { const result = await api.uploadSource(id, file); onCreated(id, result.job) }
    catch (e) { setError(String(e)); setBusy(false) }
  }
  return <div className="modal-backdrop" onMouseDown={onClose}><section className="new-run-modal" onMouseDown={(e) => e.stopPropagation()}>
    <div className="modal-head"><div><div className="eyebrow">CREATE WORKSPACE RUN</div><h2>New Run</h2></div><button className="icon-button" onClick={onClose}>×</button></div>
    <label className="field"><span>Video</span><input type="file" accept="video/*,.mp4,.mov,.avi,.mkv,.webm" onChange={(e) => { const f = e.target.files?.[0] ?? null; setFile(f); if (!runId && f) setRunId(suggestedId(f)) }} /></label>
    <label className="field"><span>Run ID</span><input value={runId} placeholder={hint || 'teddy_002'} onChange={(e) => setRunId(e.target.value)} /></label>
    <p className="form-help">视频会保存到该 Run 的 source/，随后自动执行 FFmpeg 抽帧。</p>
    {error && <div className="inline-error">{error}</div>}
    <div className="modal-actions"><button className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" onClick={submit} disabled={busy}>{busy ? 'Uploading…' : 'Create & Extract'}</button></div>
  </section></div>
}

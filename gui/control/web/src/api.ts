import type { JobInfo, MeshSettings, RunDetail, RunSummary, SplatSettings } from './types'

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try { const body = await response.json(); if (body?.detail) detail = String(body.detail) } catch {}
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

const encode = encodeURIComponent
export const api = {
  runs: () => json<RunSummary[]>('/api/runs'),
  run: (id: string) => json<RunDetail>(`/api/runs/${encode(id)}`),
  activeJob: (id: string) => json<JobInfo | null>(`/api/runs/${encode(id)}/job`),
  uploadSource: (id: string, file: File) => json<{ run_id: string; source: string; job: JobInfo }>(
    `/api/runs/${encode(id)}/source?filename=${encode(file.name)}`,
    { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file },
  ),
  mask: (id: string, box: [number, number, number, number]) => json<JobInfo>(`/api/runs/${encode(id)}/mask`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ box }),
  }),
  routeMesh: (id: string, settings: MeshSettings) => json<JobInfo>(`/api/runs/${encode(id)}/route/mesh`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings),
  }),
  routeSplat: (id: string, settings: SplatSettings) => json<JobInfo>(`/api/runs/${encode(id)}/route/splat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings),
  }),
  job: (id: string) => json<JobInfo>(`/api/jobs/${encode(id)}`),
  cancelJob: (id: string) => json<JobInfo>(`/api/jobs/${encode(id)}/cancel`, { method: 'POST' }),
  shutdown: () => json<{ status: string }>('/api/system/shutdown', { method: 'POST' }),
}

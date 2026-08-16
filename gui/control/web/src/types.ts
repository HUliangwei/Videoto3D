export type RouteSummary = 'COMPLETE' | 'IN PROGRESS' | 'PENDING' | 'BLOCKED'

export interface RunSummary {
  run_id: string
  status: string
  frames: number | string
  shared_status: string
  mesh_status: RouteSummary
  splat_status: RouteSummary
  updated_at: string
  assets: { glb: boolean; splat: boolean }
}

export interface RunDetail {
  run_id: string
  root: string
  created_at?: string
  updated_at?: string
  source: Record<string, unknown>
  shared: Record<string, any>
  routes: { mesh: Record<string, any>; splat: Record<string, any> }
  quality: any | null
  assets: { glb?: string; splat?: string }
  paths?: RuntimePaths
}

export interface RuntimePaths {
  project: { root: string; workspace: string; runtime: string }
  environments: { core: string; seg: string; gui: string }
  tools: Record<string, { path: string; source: string }>
  run: Record<string, string>
}

export type JobStatus = 'running' | 'succeeded' | 'failed' | 'cancelled'
export type ProgressStageStatus = 'done' | 'active' | 'pending' | 'error' | 'cancelled'
export interface ProgressStage {
  key: string
  label: string
  status: ProgressStageStatus
}
export interface JobProgress {
  mode: 'determinate' | 'stage'
  label: string
  detail: string
  current?: number | null
  total?: number | null
  percent?: number | null
  stage_key?: string
  stages: ProgressStage[]
}
export interface JobInfo {
  job_id: string
  run_id: string
  kind: string
  status: JobStatus
  lines: string[]
  returncode?: number | null
  started_at?: string
  finished_at?: string | null
  log_path?: string
  progress?: JobProgress
}

export interface SplatSettings {
  steps: number
  max_splats: number
  max_resolution: number
  foreground_ratio: number
  min_foreground_observations: number
  cleanup_ratio: number
  cleanup_min_views: number
}

export interface MeshSettings {
  undistort_max_image_size: number
  dense_resolution_level: number
  dense_number_views: number
  dense_max_threads: number
  refine_resolution_level: number
}

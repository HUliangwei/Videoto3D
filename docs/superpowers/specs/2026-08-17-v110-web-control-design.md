# Videoto3D V1.1 Web Control Design

## Goal
Turn the V1.0 read-only Studio into the primary local controller without duplicating reconstruction logic: browser creates runs, uploads a source video, selects a SAM2 ROI, launches Mesh/Splat routes, follows live logs, and previews final GLB/PLY assets.

## Boundaries
- `pipeline/` remains the single reconstruction implementation.
- `gui/control/` is Videoto3D-specific and may read/write run state.
- `gui/viewer/` remains reusable and must not import Videoto3D concepts.
- GUI jobs execute `env/core/python.exe app.py ...`; the GUI server never reimplements reconstruction stages.
- Project-local `env/core`, `env/seg`, `env/gui` remain A1-managed by external Conda.

## Flow
1. Runs page: `New Run`, run id + local video file.
2. Browser streams the video body to `workspace/runs/<id>/source/<filename>` and starts `run extract` as a core background job.
3. After extraction, Run detail exposes the first frame. User drags a ROI in browser coordinates; the client converts to natural image pixels.
4. GUI launches `run mask --run <id> --box x0,y0,x1,y1`. SAM2 uses project `env/seg`; no OpenCV ROI window opens.
5. When mask is ready, Mesh and Splat route controls are enabled. Splat exposes the existing seven route parameters with current defaults.
6. Jobs run one-at-a-time per Run. Browser polls job status/logs at short cadence and refreshes run state when a job ends.
7. Existing viewer continues to show GLB and cleaned PLY.

## Job model
- GUI server owns a process manager.
- Core command uses `env/core/python.exe -u app.py ...`.
- A job stores id, run id, kind, command, status, timestamps, return code and a bounded log buffer.
- Log output is also written to `workspace/runs/<id>/logs/gui/<job-id>.log`.
- One active job per Run; conflicting starts return HTTP 409.
- Cancel sends a console-group interrupt on Windows and terminates as fallback.

## Studio lifecycle
- `Exit Studio` requests `/api/system/shutdown`.
- Ctrl+C in the outer/core process catches `KeyboardInterrupt`, requests the GUI child's shutdown endpoint, waits briefly, then terminates as fallback.
- Server refuses normal shutdown while control jobs are active to avoid orphaning reconstruction; a job can be cancelled first.

## API
- `POST /api/runs/{id}/source?filename=...` stream upload + start extract
- `GET /api/runs/{id}/frames/first`
- `POST /api/runs/{id}/mask` body `{box:[x0,y0,x1,y1]}`
- `POST /api/runs/{id}/route/mesh`
- `POST /api/runs/{id}/route/splat` with optional existing Splat parameters
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/cancel`
- existing read APIs and shutdown remain

## Safety
- Validate run ids through existing run workspace helper.
- Upload filename must be a plain filename, not a path.
- Upload writes only under that run's `source/`.
- No route control while mask is pending.
- No parallel jobs for the same run.
- No destructive delete API in V1.1.

## Testing
- CLI parse and `run mask --box` propagation.
- Streaming upload path safety and job arguments.
- Route and mask control API contract.
- Job process/log state.
- Ctrl+C graceful child shutdown helper.
- Frontend contract for New Run, ROI, route controls and live job console.
- Full Python suite, compileall, TypeScript typecheck/build on an environment with npm dependencies.

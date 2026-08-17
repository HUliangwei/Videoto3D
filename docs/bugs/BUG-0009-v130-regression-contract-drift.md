# BUG-0009 — V1.3 pre-release README and Artifact contract drift

- **Status:** Mitigated
- **Severity:** Medium
- **Detected:** 2026-08-17
- **Owner:** Videoto3D
- **Affected:** V1.2 documentation refresh → V1.3.0 pre-release validation
- **Fixed/Mitigated in:** V1.3.0 Hotfix 2
- **Upstream:** N/A

## Summary

The full regression suite reached execution successfully after the test-environment fix and reported:

```text
7 failed, 214 passed
```

Six failures were documentation contracts. The user-facing README had been intentionally simplified, but existing regression tests still require exact canonical CLI strings and several engineering-reference strings that remain valid.

The seventh failure was an Artifact Inspector contract. V1.3 intentionally adds `camera-trajectory`, while the V1.2 test asserted an exact set containing only the older artifacts.

## Symptom

Affected tests:

```text
tests/test_cli.py::TestCanonicalCLI::test_readme_contains_every_canonical_command

tests/test_docs.py::
  TestProjectDocs::test_readme_points_to_bug_registry_and_current_openmvs_mask_name
  TestProjectDocs::test_v08_docs_describe_multi_run_and_blender_glb_preview
  TestProjectDocs::test_v09_docs_describe_brush_splat_and_detached_viewers
  TestV11Docs::test_v11_docs_describe_cleanup_quality_and_raw_final_split
  TestV100Docs::test_v100_docs_define_gui_control_viewer_boundary

tests/test_gui_artifacts.py::
  ArtifactCatalogTests::test_catalog_exposes_every_pipeline_artifact_and_partial_masks
```

## Evidence

V1.3 focused tests passed before the full-suite run:

```text
9 passed
```

After BUG-0008 removed collection/dependency blockers, the full suite executed normally:

```text
7 failed, 214 passed in 9.91s
```

The remaining failures are assertion mismatches, not import/runtime failures.

## Root cause

There are two independent contract drifts.

### README contract drift

The README documentation refresh optimized for first-time users and replaced the exhaustive CLI reference with shorter examples. That removed exact strings which are still intentionally protected by `canonical_command_lines()` and historical documentation tests.

The correct fix is to keep the concise workflow but add a collapsed **Exact Canonical CLI / Compatibility Reference**. This preserves usability and executable documentation.

### Artifact contract drift

V1.3 adds the Shared artifact:

```text
Camera Trajectory
```

The production catalog is therefore supposed to contain one more key:

```text
camera-trajectory
```

The old test's exact set must be extended; production must not remove the new artifact merely to satisfy a V1.2 assertion.

## Workaround / Fix

1. Restore all current canonical CLI command strings to README in a collapsed reference block.
2. Restore durable engineering references required by documentation contracts:
   - `docs/bugs`
   - `gui/control`
   - `gui/viewer`
   - OpenMVS staged mask name `frame_0001.mask.png`
   - raw Splat and quality report paths.
3. Clarify Shared SfM text for Orbit vs Turntable.
4. Add Camera Trajectory to the README Shared artifact list.
5. Update `tests/test_gui_artifacts.py` expected artifact set to include `camera-trajectory`.

## Regression guard

The existing tests remain the guard:

```text
tests/test_cli.py
tests/test_docs.py
tests/test_gui_artifacts.py
tests/test_turntable_artifacts.py
tests/test_v130_frontend_contract.py
```

No assertion is removed merely to obtain a green suite.

## Verification

Package-level verification for Hotfix 2 checks:

- every V1.3 canonical CLI string is present in the patched README;
- all strings asserted by the six failing documentation contracts are present;
- deprecated `frame_0001.jpg.mask.png` is absent;
- Artifact catalog test expectation includes `camera-trajectory`;
- patch script parses as Python;
- ZIP contains no `env/`, `runtime/`, `workspace/`, `recordings/`, or `.git`.

Final Windows verification requirement:

```powershell
python -m pytest -q
cd gui
npm run build
```

## Risks / Trade-offs

The README becomes slightly longer, but the exact CLI reference is collapsed under `<details>`, so the normal first-time-user path remains compact.

## Removal condition

The exact reference may be reorganized only if `canonical_command_lines()` and documentation-contract tests are updated in the same change and preserve equivalent coverage.

## Timeline

- 2026-08-17 — Full suite executes: 214 passed, 7 contract failures.
- 2026-08-17 — Failures classified into README drift (6) and V1.3 Artifact set expansion (1).
- 2026-08-17 — V1.3.0 Hotfix 2 prepared.

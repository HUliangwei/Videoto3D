# V0.7.2 OpenMVS Mask Naming Hotfix

**Goal:** Fix OpenMVS mask staging so `frame_0001.jpg` maps to `frame_0001.mask.png`.

**Root cause:** V0.7 staging used `frame.name + ".mask.png"`, creating `frame_0001.jpg.mask.png`, while DensifyPointCloud 2.4.0 requested `frame_0001.mask.png` at runtime.

**Constraints:** Keep SAM2 source masks unchanged as `frame_0001.jpg.png`; only change the OpenMVS staging filename. Existing stage cache must remain reusable. README must be updated with every ZIP.

**Verification:** Regression test for exact staged filename, full unit suite, compileall, fresh ZIP overlay verification.

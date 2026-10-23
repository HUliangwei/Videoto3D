# Turntable R0.2 Research Checkpoint

## R0.2a measured result on `chair_nonuniform_280`

```text
angle MAE              0.175304 deg
increment MAE          0.059716 deg
span error             0.120000 deg
monotonic violations   0
```

Representative pair errors:

```text
0 -> 1    0.018735 deg
20 -> 21  0.006796 deg
44 -> 45  0.003073 deg
```

This supports only the R0.2a claim: with correct shared geometry,
structured Essential fitting can recover non-uniform relative
Turntable angles accurately on the synthetic benchmark.

## R0.2b-1 question

With signed GT delta angles fixed, can selected image pairs jointly
recover one shared axis and one epipolar-observable transverse orbit
direction without using GT axis/orbit during fitting?

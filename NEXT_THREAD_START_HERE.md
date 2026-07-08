# Next Thread Start Here

Read this first:

```text
IMPLEMENTATION_HANDOFF_2026-07-08.md
```

Then read the implementation plan:

```text
docs/superpowers/plans/2026-07-08-runpod-productization.md
```

Critical reminder:

```text
Do not restart model/provider research.
Do not change the known-good LatentSync recipe.
Do not process the unstable 4-6s section for the next paid rerun.
The first paid rerun should use 1x A40 and only process 6-13s.
```

Known-good recipe:

```text
LatentSync
configs/unet/stage2.yaml
10 inference steps
guidance_scale 1.5
enable_deepcache
16k mono WAV audio
preserve original full-MV audio in final stitch
```


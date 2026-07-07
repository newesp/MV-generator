# Implementation Handoff - 2026-07-07

## Current Goal

Productize the validated LatentSync MVP into the existing MV Generator app.

The next implementation target is a semi-automatic RunPod provider for an
existing MV workflow:

```text
full MV mp4 + one or more lip-sync time ranges
  -> extract each target segment
  -> run LatentSync on RunPod
  -> stitch processed segments back into the full MV
  -> final MP4
```

The first UI version should support timeline selection plus numeric start/end
fields. Multiple target ranges must be supported, for example `6-13s` and
`16-23s`.

## Validated MVP Result

Local final artifact:

```text
outputs/Gina-MV_4_13_lipsync_mvp.mp4
```

Validation:

```text
duration: 28.672s
video: 1280x720, 24fps
audio: original 48kHz stereo track
```

Actual stitching strategy:

```text
0-6s   original Gina-MV.mp4
6-13s  LatentSync processed segment
13s+   original Gina-MV.mp4
```

Reason: the requested `4-13s` target range contains an unstable collage/multi-face
section around `4-6s`. Direct LatentSync on the full `4-13s` segment failed with
`RuntimeError: Face not detected`. The stable single-face section starts around
`6s`, so the MVP keeps `4-6s` original and only replaces `6-13s`.

## Important Local Files

```text
backend/src/mouth_tracking.py
backend/scripts/run_dynamic_mouth_composite.py
tests/test_mouth_tracking.py
notebooks/DYNAMIC_MOUTH_TRACKING_MVP.md
notebooks/LATENTSYNC_COLAB_MVP.md
PLANNING_LATENTSYNC_2026-07-05.md
README.md
```

`inputs/` and `outputs/` are intentionally gitignored except `.gitkeep`.

## RunPod State From MVP

RunPod Jupyter URL used during the MVP:

```text
https://rug1jzihg85ujj-8888.proxy.runpod.net/lab
```

LatentSync environment on RunPod:

```text
/workspace/LatentSync
/workspace/LatentSync/checkpoints/latentsync_unet.pt
/workspace/LatentSync/checkpoints/whisper/tiny.pt
```

Generated remote segment:

```text
/workspace/gina_mv_6_13_latentsync_direct.mp4
```

The temporary HTTP server used for transfer was stopped, and the temporary
transfer HTML was deleted after download.

## Recommended Next Architecture

Keep the current image-to-MV flow, but add a second workflow:

```text
Image MV
Lip-sync Existing MV
```

The new workflow should use a job model instead of the current single global
`generation_status`.

Suggested job state:

```json
{
  "job_id": "uuid",
  "workflow": "lipsync_existing_mv",
  "status": "running",
  "stage": "latentsync",
  "progress": 0.62,
  "message": "Running segment 1 of 2 on RunPod",
  "artifacts": {
    "final": "outputs/job-id/final.mp4"
  }
}
```

## Semi-Automatic Provider Definition

The app automates local work:

```text
upload MV
set one or more ranges
validate media
extract video/audio segments
prepare RunPod command bundle
accept processed segment artifacts
stitch segments back into full MV
verify final MP4
```

RunPod inference remains manual or Codex-assisted at first:

```text
copy/upload prepared segments to RunPod
run LatentSync in Jupyter
download processed segments
resume local stitching
```

The next upgrade is a full RunPod worker API so the backend can submit jobs
directly without Jupyter.

## Proposed Implementation Order

1. Add backend job model and status endpoints.
2. Add media utilities for validation, segment extraction, and stitching.
3. Add `lipsync_existing_mv` pipeline with a manual provider boundary.
4. Add UI mode switch and Existing MV form.
5. Add timeline plus start/end fields and multiple ranges.
6. Add result preview/download and intermediate artifact visibility.
7. Replace manual provider with RunPod API worker when stable.

## Verification Commands Used

```powershell
backend\venv\Scripts\python.exe -m unittest tests.test_mouth_tracking -v
backend\venv\Scripts\python.exe backend\scripts\run_dynamic_mouth_composite.py --help
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate,sample_rate,channels -of compact=p=0:nk=1 outputs\Gina-MV_4_13_lipsync_mvp.mp4
```

The final output was also spot-checked with extracted frames at `5s`, `8.5s`,
and `14s`.

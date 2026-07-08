# Implementation Handoff - 2026-07-08

Read this file first when resuming the MV Generator project. It records the
known-good lip-sync recipe, the failures that must not be rediscovered, and the
next productization path.

## Hard Rule

Do not restart model/provider research from scratch.

The project already has one validated LatentSync MVP that can lip-sync the
stable section of `inputs/Gina-MV.mp4`. Preserve that recipe unless a new test
proves a better one.

## Current Pause State

The user paused paid RunPod work on 2026-07-08. No new A40 Pod was deployed.

RunPod deploy page state at pause:

```text
Template: Runpod Pytorch 2.8.0
Selected GPU: 1x A40
GPU price: $0.44/hr
Total price shown by UI: $0.45/hr
VRAM: 48GB
RAM: 50GB
vCPU: 9
Deploy blocked because account balance was -$0.02.
RunPod message: You must have at least $0.08 in order to deploy this Pod.
```

GPU decision:

```text
A40: recommended for first paid rerun. 48GB VRAM, available, about $0.45/hr total.
RTX A5000: cheaper at about $0.28/hr total, but was out of capacity.
RTX 4090: available, 24GB VRAM, but more expensive at about $0.70/hr total.
```

Do not click checkout, add funds, enable auto-pay, or deploy a paid Pod without
explicit user approval.

## Validated MVP

Validated local output:

```text
outputs/Gina-MV_4_13_lipsync_mvp.mp4
```

Final media properties:

```text
duration: 28.672s
video: 1280x720, 24fps
audio: original 48kHz stereo track
```

Actual successful splice:

```text
0-6s    original source video
6-13s   LatentSync processed segment
13s+    original source video
```

Important: the user originally asked for `4-13s`, but `4-6s` contains unstable
collage/multi-face content. Direct LatentSync on `4-13s` failed with
`RuntimeError: Face not detected`. The stable single-face section starts around
`6s`. For the current MVP, keep `4-6s` original and process only `6-13s`.

## Known-Good LatentSync Recipe

Use this exact recipe before changing anything:

```bash
cd /workspace/LatentSync
python3 -m scripts.inference \
  --unet_config_path configs/unet/stage2.yaml \
  --inference_ckpt_path checkpoints/latentsync_unet.pt \
  --inference_steps 10 \
  --guidance_scale 1.5 \
  --enable_deepcache \
  --video_path input_segments/<job>/range_001_source.mp4 \
  --audio_path input_audio/<job>/range_001_audio.wav \
  --video_out_path output_segments/<job>/range_001_processed.mp4
```

Required local segment preparation:

```text
video segment: mp4, source fps normalized later during stitch
audio segment: wav, pcm_s16le, 16000 Hz, mono
```

Do not regress to these failed choices:

```text
configs/unet/stage2_512.yaml
20 inference steps
m4a segment audio
processing the unstable 4-6s collage section
HF demo Spaces as the production provider
```

## Failures Already Diagnosed

These are known dead ends or partial failures:

```text
LivePortrait HF Space:
  Not audio-driven. The inspected API is image/video driven, not suitable for
  "image or MV + mp3 -> lip-sync".

SadTalker HF:
  Useful only as early exploration. Spaces were unstable or too slow.

Wav2Lip HF:
  Produced poor quality for this MV target.

MuseTalk HF Spaces:
  Several demos produced debug overlays, green detection boxes, mosaic layouts,
  or video without reliable lip-sync.

MuseTalk 1.5 Colab:
  Reduced some issues but still blurred the face too much for the target MV.

LatentSync 16:9 paste-back experiments:
  Static paste-back can drift badly when face position changes. The only clean
  MVP came from using the stable 6-13s section and stitching it back into the
  full original MV.
```

Specific regression that already happened:

```text
A later thread changed the recipe to stage2_512.yaml + 20 steps + m4a audio.
That broke the visual result. Do not repeat that change.
```

## Current Code State

The repo currently contains an existing-MV lip-sync workflow.

Primary backend files:

```text
backend/main.py
backend/src/job_store.py
backend/src/lipsync_existing_mv.py
backend/src/runpod_latentsync.py
```

Primary frontend files:

```text
frontend/src/App.jsx
frontend/src/index.css
frontend/src/lipsyncRanges.js
frontend/src/sourcePreview.js
```

Primary tests:

```text
tests/test_job_store.py
tests/test_lipsync_api.py
tests/test_lipsync_existing_mv.py
tests/test_runpod_latentsync.py
frontend/src/lipsyncRanges.test.js
frontend/src/sourcePreview.test.js
```

Current backend endpoint:

```text
POST /lipsync-existing-mv
GET  /jobs/{job_id}
GET  /jobs/{job_id}/download/final
POST /jobs/{job_id}/processed-segments/{segment_index}
POST /jobs/{job_id}/resume-stitch
```

The app supports:

```text
Lip-sync Existing MV mode
timeline selection
numeric start/end fields
multiple ranges
local segment extraction
local stitch/verify
automatic RunPod Jupyter provider skeleton
manual processed-segment fallback
```

The automatic provider currently expects an already-running Jupyter Pod with:

```text
RUNPOD_JUPYTER_BASE_URL=https://<pod>-8888.proxy.runpod.net
RUNPOD_JUPYTER_TOKEN=<jupyter token>
RUNPOD_LATENTSYNC_ROOT=/workspace/LatentSync
RUNPOD_LATENTSYNC_TIMEOUT_SECONDS=1800
```

The provider assumes `/workspace/LatentSync` already exists on the Pod and that
the required checkpoints are already present. A fresh Pod may need a bootstrap
step before E2E can run.

## Fixes Already Applied

Important fixes in the current working tree:

```text
backend/src/lipsync_existing_mv.py:
  - extracts segment audio as 16k mono WAV
  - normalizes processed segment duration with -t <range_duration>
  - preserves original full-MV audio during final stitch with -c:a copy
  - writes concat file entries as absolute paths to avoid outputs/outputs bugs

backend/src/runpod_latentsync.py:
  - uses stage2.yaml, 10 steps, guidance 1.5, enable_deepcache
  - checks Jupyter API health before upload
  - supports Contents API roots mapped as workspace/LatentSync or LatentSync

frontend/src/App.jsx:
  - starts automatic RunPod job
  - polls /jobs/{job_id}
  - displays final download when completed
  - keeps manual fallback visible only for waiting_manual jobs
```

## Verification Evidence Before Pause

Fresh verification passed after the current code changes:

```powershell
backend\venv\Scripts\python.exe -m unittest discover -s tests -v
# 21 tests passed

node --test frontend/src/lipsyncRanges.test.js frontend/src/sourcePreview.test.js
# 8 tests passed

npm.cmd run build
# passed
```

Local stitch regression check passed using the known-good processed 6-13s
segment:

```text
outputs/debug_restitch_from_success.mp4
duration: 28.666667s
video: 1280x720, 24fps
audio: 48000 Hz stereo
```

This file is a debug output and should not be committed unless intentionally
converted into a fixture.

## Resume Checklist

When resuming in a new thread:

1. Read this file first.
2. Run `git status --short`.
3. Do not revert user/predecessor changes.
4. Run the verification commands above before changing behavior.
5. Confirm whether the user wants to pay for RunPod now.
6. If yes, deploy `1x A40` first for the quality rerun.
7. Before running E2E, confirm `/workspace/LatentSync` exists on the Pod.
8. If LatentSync is missing, bootstrap the Pod before submitting a job.
9. Run only the stable `6-13s` range for the first paid test.
10. Compare the output against `outputs/Gina-MV_4_13_lipsync_mvp.mp4`.

Do not spend time re-evaluating HF Spaces unless LatentSync is explicitly
abandoned by the user.

## Next Productization Path

The current Jupyter provider is not product-ready because the proxy URL and Pod
lifecycle are manual. Productization path:

```text
Phase 1: Paid A40 rerun
  - deploy A40 only after explicit user approval
  - bootstrap /workspace/LatentSync if needed
  - run the existing automatic provider on 6-13s
  - verify final quality and audio/video duration

Phase 2: RunPod API auto start/stop + local job queue
  - backend owns Pod lifecycle
  - users never see Jupyter URLs
  - persistent local job state replaces in-memory JobStore
  - idle Pod is stopped automatically
  - failures are resumable

Phase 3: RunPod Serverless Endpoint
  - LatentSync and checkpoints are baked into a Docker image or mounted cache
  - backend submits segment jobs to a stable endpoint
  - object storage handles large video/audio artifacts
  - worker scales to zero and returns processed segments
```

See also:

```text
docs/superpowers/plans/2026-07-08-runpod-productization.md
IMPLEMENTATION_HANDOFF_2026-07-07.md
PLANNING_LATENTSYNC_2026-07-05.md
```


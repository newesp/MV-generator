# Dynamic Mouth Tracking MVP

This is the next experiment after the fixed-coordinate LatentSync mouth patch.
The goal is to stop pasting a mouth patch into a hard-coded 16:9 position and
instead track the mouth in each base frame.

## Why

The fixed patch used a stable LatentSync crop but pasted it back at a constant
position in the 16:9 MV. That fails when the MV cuts to a different shot, when
the subject turns sideways, or when the mouth moves away from the original crop.

This MVP uses MediaPipe Face Mesh to detect mouth landmarks in:

- the 16:9 base frame; and
- the LatentSync cropped face layer.

It then resizes the source mouth patch into the target mouth box, applies a soft
ellipse mask, color-matches the patch to the target ROI, and writes a composited
MP4.

## Files

```text
backend/src/mouth_tracking.py
backend/scripts/run_dynamic_mouth_composite.py
tests/test_mouth_tracking.py
```

The geometry core is tested with standard-library `unittest` so the tests can
run locally without installing OpenCV or MediaPipe.

## Local Tests

```powershell
backend\venv\Scripts\python.exe -m unittest tests.test_mouth_tracking -v
backend\venv\Scripts\python.exe backend\scripts\run_dynamic_mouth_composite.py --help
```

## RunPod Short Debug

Run this after the LatentSync crop layer exists on RunPod:

```bash
python3 /workspace/backend/scripts/run_dynamic_mouth_composite.py \
  --base-video /workspace/gina_base_with_audio.mp4 \
  --face-layer /workspace/latentsync_gina_30s_loop_mvp.mp4 \
  --audio /workspace/Café_no_Mar.mp3 \
  --output /workspace/gina_dynamic_mouth_tracking_8s_debug.mp4 \
  --max-seconds 8 \
  --preview-dir /workspace/dynamic_mouth_preview \
  --preview-every 48 \
  --debug-overlay \
  --alpha 1.0
```

The first RunPod debug produced:

```text
frames_total=192
frames_composited=49
frames_skipped=143
output=/workspace/gina_dynamic_mouth_tracking_8s_debug.mp4
```

The downloaded local debug artifact is:

```text
outputs/gina_dynamic_mouth_tracking_8s_debug.mp4
```

## Current Interpretation

This approach fixes the main category of failure: the patch is no longer bound
to one fixed 16:9 coordinate. However, the first pass composites only a subset
of frames because either the base frame or the LatentSync crop frame may fail
mouth landmark detection.

That is acceptable for the first debug pass. The next iteration should improve
coverage and quality before running the full MV.

## Next Iteration

1. Save per-frame detection metrics so we know whether skipped frames come from
   the base video, the source crop, or both.
2. Choose the primary base face by temporal continuity, not just largest mouth
   box.
3. Add a quality gate for side faces and occlusions, especially drinking shots.
4. Cache and smooth source mouth boxes separately so brief source detection
   misses do not skip otherwise usable frames.
5. Consider a landmark-triangle or thin-plate warp once mouth-box tracking is
   stable.

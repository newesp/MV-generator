# LatentSync MVP Status - 2026-07-05

## Current Working Path

```text
outputs/gina_base_with_audio.mp4 + inputs/Cafe_no_Mar.mp3
  -> Google Colab LatentSync 1.5
  -> cropped main-face lip-sync MP4
```

## Validated

- Public Hugging Face Wav2Lip/MuseTalk endpoints were not production-stable for this MVP.
- MuseTalk Colab 1.5 ran, but the output looked blurry.
- LatentSync 1.5 was installed in Colab with a `latentsync` conda environment.
- Weights downloaded from `ByteDance/LatentSync-1.5`:
  - `checkpoints/latentsync_unet.pt`
  - `checkpoints/whisper/tiny.pt`
- Raw `gina_base_with_audio.mp4` failed with:

```text
RuntimeError: Face not detected
```

## Root Cause

The base video contains both:

- a top-left picture-in-picture face; and
- the primary face in the main 16:9 frame.

LatentSync face detection failed on the raw 16:9 video and on a loose upper-body crop. A tighter crop that removes the picture-in-picture face and centers the primary face fixed the 2 second smoke test.

## Working Crop

```text
crop=320:320:480:20,scale=512:512
```

Successful smoke-test output in Colab:

```text
/content/latentsync_gina_2s_mainface.mp4
```

## Current Blocker

Colab GPU quota is exhausted / disconnected before the 30 second MVP could be generated.

## Next Actions

1. Preserve/download the successful 2 second output if the Colab runtime is still alive.
2. When GPU is available again, run the 30 second command in `notebooks/LATENTSYNC_COLAB_MVP.md`.
3. For productization, move LatentSync to a reproducible GPU host such as RunPod, or regenerate the base video as a single close-up face without the picture-in-picture overlay.

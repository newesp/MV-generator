# LatentSync MVP Status - 2026-07-05

## Current Working Path

```text
outputs/gina_base_with_audio.mp4 + inputs/Cafe_no_Mar.mp3
  -> Google Colab LatentSync 1.5
  -> cropped main-face lip-sync MP4
  -> 16:9 mouth-patch composite MP4
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
- The 2 second tight-crop smoke test succeeded.
- A direct 30 second tight-crop run still hit face-detection instability on some frames.
- A 30 second loop fallback succeeded:

```text
/content/latentsync_gina_30s_loop_mvp.mp4
```

- Full 320x320 paste-back into the 16:9 base video created a visible rectangular artifact and replaced hair/clothing/background.
- A smaller low-position mouth/lower-face alpha patch produced the cleanest 16:9 MVP preview:

```text
/content/gina_latentsync_16x9_mouth_low_mvp.mp4
```

- User review noted that the "cleanest" low-mouth version was too transparent and looked mostly like the original video.
- Increasing alpha alone exposed a yellow/bright patch, so the next candidate uses a narrower mouth mask plus color matching:

```text
/content/gina_latentsync_16x9_mouth_cc125_mvp.mp4
mask: cx=160, cy=242, rx=58, ry=24, alpha=1.25
color match: LatentSync patch mean/std matched to base ROI inside the active mask
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

The current 16:9 MVP is visually cleaner than the cropped output, but it is still a composition prototype:

- the face layer is generated from a 2 second loop fallback, not a natural 30 second close-up;
- the mouth patch uses fixed coordinates instead of landmark tracking;
- the low-mouth alpha-only patch is too subtle, while stronger alpha needs color matching; and
- full-face paste-back is not viable because LatentSync's output crop is not spatially stable enough to overlay as a full square.

## Next Actions

1. Download `/content/gina_latentsync_16x9_mouth_low_mvp.mp4` from Colab.
2. Update the notebook workflow to prefer 16:9 mouth-patch compositing over cropped close-up delivery.
3. Productize by replacing fixed mouth coordinates with face-landmark tracking.
4. Regenerate the base video as a single stable main-face shot without picture-in-picture overlay.
5. Move LatentSync to a reproducible GPU host such as RunPod when Colab iteration is no longer enough.

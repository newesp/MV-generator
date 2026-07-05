# MV Generator

AI MV Generator is a local MVP for turning audio and image assets into a music video.

The current stable path is:

1. Analyze audio with `librosa`.
2. Split the song into predictable sections or beat-based segments.
3. Reuse uploaded images as visual assets.
4. Try lip-sync/talking-head generation through a Hugging Face Space.
5. Fall back to static image clips when lip-sync fails.
6. Merge clips with the original audio through FFmpeg.

## Project Structure

```text
backend/   FastAPI API and media pipeline
frontend/  Vite + React UI
inputs/    Local upload staging directory
outputs/   Generated videos and temporary media
```

## Backend

```powershell
cd backend
venv\Scripts\python.exe -m uvicorn main:app --reload
```

The backend expects FFmpeg and FFprobe to be available on `PATH`.

## Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

## Current Limits

- The default lip-sync provider is `fatma812/Wav2lip-ZeroGPU2`.
- The MVP output is limited to the first 30 seconds by default.
- A 28.66s MVP test using `inputs\Gina (1).png` and `inputs\Café_no_Mar.mp3` successfully generated `outputs\final_mv.mp4`.
- `kevinwang676/SadTalker` remains available as a configurable provider, but a 0.75s test clip entered prediction and did not return within 10 minutes.
- Official LivePortrait is video-driven, not audio-driven, so it is kept only as an experimental legacy provider.
- Public Hugging Face MuseTalk demos produced debug overlays, returned no result, or blocked result downloads. The working MVP path now uses self-managed Colab LatentSync with a main-face crop.

## Colab LatentSync MVP

Use the Colab workflow in [notebooks/LATENTSYNC_COLAB_MVP.md](notebooks/LATENTSYNC_COLAB_MVP.md).

Companion instructions are in [notebooks/README.md](notebooks/README.md).

The intended flow is:

```text
outputs/gina_base_with_audio.mp4 + inputs/Café_no_Mar.mp3
  -> Colab LatentSync
  -> latentsync_gina_30s_mainface.mp4
```

The first successful smoke test used a 2 second cropped main-face clip:

```text
crop=320:320:480:20,scale=512:512
```
- Fal.ai video generation is not wired in yet.
- The default segmentation mode is `sections` to keep runtime and API usage predictable.
- The app currently supports a single local generation job at a time.

## Talking-Head Space Inspection

Inspect a candidate Hugging Face Space before wiring it into the full pipeline:

```powershell
backend\venv\Scripts\python.exe backend\scripts\test_lipsync_space.py --space-id owner/space-name
```

Run a small prediction test:

```powershell
backend\venv\Scripts\python.exe backend\scripts\test_lipsync_space.py --space-id fatma812/Wav2lip-ZeroGPU2 --provider wav2lip_zerogpu_hf --predict --image inputs\portrait.png --audio outputs\segment_000.m4a
```

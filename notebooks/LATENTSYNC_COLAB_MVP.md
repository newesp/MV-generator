# LatentSync Colab MVP

This is the current working MVP path after the public Hugging Face and MuseTalk tests:

```text
outputs/gina_base_with_audio.mp4 + inputs/Cafe_no_Mar.mp3
  -> Colab LatentSync
  -> cropped main-face lip-sync MP4
  -> optional 16:9 mouth-patch composite MP4
```

The first successful validation was a 2 second clip using a main-face crop:

```text
crop=320:320:480:20,scale=512:512
```

This crop intentionally removes the picture-in-picture face in the top-left of the base video and keeps only the primary face. Without this crop, LatentSync failed with:

```text
RuntimeError: Face not detected
```

## Colab Runtime

Use a GPU runtime. Free Colab GPU availability is quota-limited; if Colab says it cannot connect to a GPU backend, wait for quota recovery or use Colab Pay As You Go / another GPU host.

If the runtime is still connected, download any generated MP4 before reconnecting or resetting.

## Setup

Run these cells in a fresh Colab runtime.

### 1. Clone LatentSync

```python
%cd /content
!git clone https://github.com/bytedance/LatentSync.git
%cd /content/LatentSync
```

### 2. Install Miniforge

```bash
%%bash
set -e
cd /content
if [ ! -x /content/conda/bin/conda ]; then
  curl -L -o Miniforge3.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
  bash Miniforge3.sh -b -p /content/conda
fi
/content/conda/bin/conda create -y -n latentsync python=3.10.13
```

### 3. Install Dependencies

```bash
%%bash
set -e
cd /content/LatentSync
/content/conda/bin/conda run --no-capture-output -n latentsync python -m pip install -U pip setuptools wheel
/content/conda/bin/conda run --no-capture-output -n latentsync python -m pip install -r requirements.txt
/content/conda/bin/conda run --no-capture-output -n latentsync python -c "import sys, torch, numpy; print(sys.version); print(torch.__version__, torch.cuda.is_available()); print(numpy.__version__)"
```

Expected environment from the successful run:

```text
python 3.10.x
torch 2.5.1+cu121
cuda True
```

### 4. Download Weights

```python
%cd /content/LatentSync
from huggingface_hub import hf_hub_download
import os

os.makedirs("checkpoints/whisper", exist_ok=True)
hf_hub_download(
    repo_id="ByteDance/LatentSync-1.5",
    filename="latentsync_unet.pt",
    local_dir="checkpoints",
    local_dir_use_symlinks=False,
)
hf_hub_download(
    repo_id="ByteDance/LatentSync-1.5",
    filename="whisper/tiny.pt",
    local_dir="checkpoints",
    local_dir_use_symlinks=False,
)
```

## Upload Inputs

Upload these two files to Colab, preferably while the current directory is `/content/LatentSync`:

```text
outputs/gina_base_with_audio.mp4
inputs/Cafe_no_Mar.mp3
```

If the video is uploaded more than once, Colab may name it:

```text
gina_base_with_audio (1).mp4
```

The commands below intentionally use `ls -t gina_base_with_audio*.mp4 | head -1` so the latest upload is used.

## 2 Second Smoke Test

Run this before attempting the full MVP. It verifies that face detection, audio loading, and inference all work.

```bash
%%bash
set -e
cd /content/LatentSync

V=$(ls -t gina_base_with_audio*.mp4 | head -1)
A=$(ls -t Caf*_Mar.mp3 | head -1)
echo "$V"
echo "$A"

ffmpeg -y -i "$V" -t 2 -an \
  -vf crop=320:320:480:20,scale=512:512 \
  -c:v libx264 -pix_fmt yuv420p \
  /content/latentsync_video_2s_mainface.mp4

ffmpeg -y -i "$A" -t 2 -ar 16000 -ac 1 \
  /content/latentsync_audio_2s.wav

export MPLBACKEND=Agg
export PYTHONUNBUFFERED=1
/content/conda/envs/latentsync/bin/python -m scripts.inference \
  --unet_config_path configs/unet/stage2.yaml \
  --inference_ckpt_path checkpoints/latentsync_unet.pt \
  --inference_steps 10 \
  --guidance_scale 1.5 \
  --enable_deepcache \
  --video_path /content/latentsync_video_2s_mainface.mp4 \
  --audio_path /content/latentsync_audio_2s.wav \
  --video_out_path /content/latentsync_gina_2s_mainface.mp4

ls -lh /content/latentsync_gina_2s_mainface.mp4
```

Preview and download:

```python
from IPython.display import Video, display
from google.colab import files

display(Video("/content/latentsync_gina_2s_mainface.mp4", embed=True, width=512))
files.download("/content/latentsync_gina_2s_mainface.mp4")
```

## 30 Second MVP

Run this only after the 2 second smoke test works.

```bash
%%bash
set -e
cd /content/LatentSync

V=$(ls -t gina_base_with_audio*.mp4 | head -1)
A=$(ls -t Caf*_Mar.mp3 | head -1)
echo "$V"
echo "$A"

ffmpeg -y -i "$V" -t 30 -an \
  -vf crop=320:320:480:20,scale=512:512 \
  -c:v libx264 -pix_fmt yuv420p \
  /content/latentsync_video_30s_mainface.mp4

ffmpeg -y -i "$A" -t 30 -ar 16000 -ac 1 \
  /content/latentsync_audio_30s.wav

export MPLBACKEND=Agg
export PYTHONUNBUFFERED=1
/content/conda/envs/latentsync/bin/python -m scripts.inference \
  --unet_config_path configs/unet/stage2.yaml \
  --inference_ckpt_path checkpoints/latentsync_unet.pt \
  --inference_steps 10 \
  --guidance_scale 1.5 \
  --enable_deepcache \
  --video_path /content/latentsync_video_30s_mainface.mp4 \
  --audio_path /content/latentsync_audio_30s.wav \
  --video_out_path /content/latentsync_gina_30s_mainface.mp4

ls -lh /content/latentsync_gina_30s_mainface.mp4
```

Preview and download:

```python
from IPython.display import Video, display
from google.colab import files

display(Video("/content/latentsync_gina_30s_mainface.mp4", embed=True, width=512))
files.download("/content/latentsync_gina_30s_mainface.mp4")
```

## 30 Second Loop Fallback

The direct 30 second crop can still fail with `RuntimeError: Face not detected` on some frames. If that happens, use the successful 2 second tight crop as a stable looped face source. This is not the final product approach, but it produces a complete 30 second lip-sync face layer for compositing tests.

```python
import os
import subprocess

sh = lambda s: subprocess.run(s, shell=True, check=True)
sh("ffmpeg -y -stream_loop 20 -i /content/latentsync_video_2s_mainface.mp4 -t 30 -c:v libx264 -pix_fmt yuv420p /content/latentsync_video_30s_loop.mp4")
sh("ffmpeg -y -i '/content/Cafe_no_Mar.mp3' -t 30 -ar 16000 -ac 1 /content/latentsync_audio_30s.wav")

env = os.environ.copy()
env["MPLBACKEND"] = "Agg"
env["PYTHONUNBUFFERED"] = "1"

python = "/content/conda/envs/latentsync/bin/python"
args = (
    "--unet_config_path configs/unet/stage2.yaml "
    "--inference_ckpt_path checkpoints/latentsync_unet.pt "
    "--inference_steps 10 "
    "--guidance_scale 1.5 "
    "--enable_deepcache "
    "--video_path /content/latentsync_video_30s_loop.mp4 "
    "--audio_path /content/latentsync_audio_30s.wav "
    "--video_out_path /content/latentsync_gina_30s_loop_mvp.mp4"
).split()

subprocess.run(
    [python, "-m", "scripts.inference"] + args,
    cwd="/content/LatentSync",
    env=env,
    check=True,
)
print("OK", os.path.getsize("/content/latentsync_gina_30s_loop_mvp.mp4"))
```

## 16:9 MV Composite MVP

The product target is a 16:9 MV, not a cropped face video. The validated short-term route is:

1. keep the original 16:9 base video as the master frame;
2. run LatentSync on the stable face crop;
3. paste only a small soft mouth/lower-face patch back into the master frame; and
4. mux the original song audio into the final MP4.

Do not paste the full 320x320 face crop back into the 16:9 frame. That replaces hair, clothing, and background and creates a visible rectangular artifact.

The first low-position mouth mask was visually clean but too transparent, so it looked almost identical to the original video. Raising opacity without color correction creates a yellow/bright patch because the LatentSync face crop does not match the 16:9 base frame's color. The next candidate should use a narrower mouth mask plus per-frame color matching before blending:

```text
mask center: cx=160, cy=242
mask radius: rx=58, ry=24
alpha scale: 1.25
color match: patch mean/std -> base ROI mean/std inside the active mask
```

Reference Colab output name for this candidate:

```text
/content/gina_latentsync_16x9_mouth_cc125_mvp.mp4
```

The earlier low-position mouth-mask prototype used:

```python
import os
import subprocess
import cv2
import numpy as np

base = "/content/gina_base_with_audio.mp4"
face = "/content/latentsync_gina_30s_loop_mvp.mp4"
audio = "/content/Cafe_no_Mar.mp3"
base30 = "/content/gina_base30_silent.mp4"
silent = "/content/gina_latentsync_16x9_mouth_low_silent.mp4"
out = "/content/gina_latentsync_16x9_mouth_low_mvp.mp4"
preview = "/content/gina_latentsync_16x9_mouth_low_preview_15s.jpg"

subprocess.run([
    "ffmpeg", "-y", "-stream_loop", "1", "-i", base, "-t", "30",
    "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", base30,
], check=True)

B = cv2.VideoCapture(base30)
F = cv2.VideoCapture(face)
fps = B.get(cv2.CAP_PROP_FPS) or 24
ffps = F.get(cv2.CAP_PROP_FPS) or fps
W = int(B.get(cv2.CAP_PROP_FRAME_WIDTH))
H = int(B.get(cv2.CAP_PROP_FRAME_HEIGHT))
N = int(round(30 * fps))

x, y, w, h = 480, 20, 320, 320
O = cv2.VideoWriter(silent, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

yy, xx = np.mgrid[0:h, 0:w]
cx, cy, rx, ry = 160, 235, 68, 34
d = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
alpha = np.clip(1 - d, 0, 1) ** 1.5
alpha = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), 11)[:, :, None] * 0.75

last = None
saved = False
for i in range(N):
    ok, frame = B.read()
    if not ok:
        break

    F.set(cv2.CAP_PROP_POS_FRAMES, int(round((i / fps) * ffps)))
    ok2, patch = F.read()
    if not ok2:
        patch = last
    if patch is None:
        break
    last = patch

    patch = cv2.resize(patch, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)
    roi = frame[y:y + h, x:x + w].astype(np.float32)
    frame[y:y + h, x:x + w] = np.clip(patch * alpha + roi * (1 - alpha), 0, 255).astype(np.uint8)

    if (not saved) and i >= int(15 * fps):
        cv2.imwrite(preview, frame)
        saved = True
    O.write(frame)

B.release()
F.release()
O.release()

subprocess.run([
    "ffmpeg", "-y", "-i", silent, "-i", audio, "-t", "30",
    "-map", "0:v:0", "-map", "1:a:0",
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-shortest", out,
], check=True)

print("OK", os.path.getsize(out), out)
print("PREVIEW", preview, os.path.getsize(preview))
```

Preview and download:

```python
from IPython.display import Image, Video, display
from google.colab import files

img = "/content/gina_latentsync_16x9_mouth_low_preview_15s.jpg"
vid = "/content/gina_latentsync_16x9_mouth_low_mvp.mp4"
display(Image(img, width=640))
display(Video(vid, embed=True, width=640))
files.download(vid)
```

## Known Issues

- Free Colab GPU quota can disconnect or refuse new GPU backends.
- Do not rerun dependency installation unless the runtime was reset.
- The current output is a cropped close-up MVP, not the final 16:9 MV composition.
- The base video contains a top-left picture-in-picture face, which confused LatentSync until the main-face crop was applied.
- If `matplotlib` reports a backend error, make sure inference uses `export MPLBACKEND=Agg`.
- Full-face 16:9 paste-back creates a visible rectangular artifact. Use a small mouth/lower-face alpha patch instead.
- The loop fallback is useful for product-composition testing, but it is not a final natural-motion solution.

## Next Product Step

After validating the 16:9 mouth-patch MVP:

1. replace the fixed mouth mask with face-landmark alignment;
2. regenerate the base video without the picture-in-picture overlay; or
3. run LatentSync on a product-grade stable close-up and composite it into the 16:9 MV.

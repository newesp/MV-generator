# LatentSync Colab MVP

This is the current working MVP path after the public Hugging Face and MuseTalk tests:

```text
outputs/gina_base_with_audio.mp4 + inputs/Cafe_no_Mar.mp3
  -> Colab LatentSync
  -> cropped main-face lip-sync MP4
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

## Known Issues

- Free Colab GPU quota can disconnect or refuse new GPU backends.
- Do not rerun dependency installation unless the runtime was reset.
- The current output is a cropped close-up MVP, not the final 16:9 MV composition.
- The base video contains a top-left picture-in-picture face, which confused LatentSync until the main-face crop was applied.
- If `matplotlib` reports a backend error, make sure inference uses `export MPLBACKEND=Agg`.

## Next Product Step

After generating the cropped 30 second MVP, either:

1. paste the lip-synced face crop back into the original 16:9 base video, or
2. regenerate the base video as a stable main-face close-up without the picture-in-picture overlay.

# Colab MVP Workflows

The current working MVP path is LatentSync:

```text
local base MP4 + MP3 -> Colab LatentSync -> cropped main-face lip-sync MP4
```

Use:

```text
LATENTSYNC_COLAB_MVP.md
```

The MuseTalk notebook is kept as an older reference path.

This folder contains the Colab workflow for the current clean-output MVP:

```text
local Gina clips -> local base MP4 + MP3 -> Colab MuseTalk -> final lip-sync MP4
```

## Why Colab

Public Hugging Face demos were useful for API probing, but they produced debug overlays, returned no result, or blocked result downloads. Colab lets us run the open-source model directly and control the output files.

## Rights And Safety

The current assets are AI-generated, which reduces many conventional licensing risks. Still verify:

- the generation platform terms allow the intended commercial or public use;
- the generated character is not intentionally imitating a real person's likeness;
- the music/audio source is licensed for the intended use;
- the output is labeled or handled appropriately for your target platform.

## Local Prep

The current local prep commands already produced:

- `outputs/gina_base_silent.mp4`
- `outputs/gina_base_with_audio.mp4`

For Colab, upload these two files:

- `outputs/gina_base_with_audio.mp4`
- `inputs/Café_no_Mar.mp3`

The notebook will also accept freshly uploaded files with different names if you update the path variables.

## Notebook

Open:

```text
MV_MuseTalk_Colab.ipynb
```

In Colab:

1. Runtime -> Change runtime type -> GPU.
2. Run the environment check cell.
3. Clone MuseTalk and install dependencies.
4. Download model weights.
5. Upload the base MP4 and MP3.
6. Normalize inputs.
7. Run inference.
8. Merge the original MP3 back into the generated video if needed.
9. Preview/download the final MP4.

## Expected Output

The notebook writes results under:

```text
/content/MuseTalk/results/mv_mvp/
```

The final downloadable file is:

```text
/content/musetalk_colab_final_with_audio.mp4
```

## Notes

- MuseTalk recommends 25fps input video. The notebook converts the uploaded base video to 25fps before inference.
- Colab free GPU availability is not guaranteed and sessions may disconnect.
- The first run is slow because dependencies and model weights need to download.
- Current Colab runtimes may use Python 3.12, but MuseTalk's official dependencies expect Python 3.10-compatible wheels. The notebook creates a separate conda environment named `musetalk` with Python 3.10 and runs inference through that environment.
- The notebook downloads weights directly with `huggingface_hub.snapshot_download()` and `gdown.download()` because MuseTalk's upstream `download_weights.sh` currently uses a Hugging Face mirror and old `gdown --id` syntax that can fail in Colab.
- MuseTalk inference sets `MPLBACKEND=Agg` to avoid Colab/conda matplotlib backend errors from `mmpose`.

## If Install Dependencies Fails

The old install cell failed because:

- `torch==2.0.1` does not provide Python 3.12 wheels in the selected CUDA index;
- `numpy==1.23.5` cannot install cleanly on Python 3.12;
- old `setuptools/pkg_resources` code references `pkgutil.ImpImporter`, which was removed in Python 3.12.

Use the updated notebook and re-run from the **Install Dependencies** cell in a fresh Colab runtime.

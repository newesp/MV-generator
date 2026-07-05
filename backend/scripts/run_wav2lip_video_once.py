import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.lipsync import generate_wav2lip_file_video  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Run Wav2Lip once with a source video/image and audio file.")
    parser.add_argument("--video", required=True, help="Source video or image path")
    parser.add_argument("--audio", required=True, help="Driving audio path")
    parser.add_argument("--space-id", default="manavisrani07/gradio-lipsync-wav2lip")
    parser.add_argument("--api-name", default="/generate")
    parser.add_argument("--checkpoint", default="wav2lip_gan", choices=["wav2lip", "wav2lip_gan"])
    parser.add_argument("--pad-top", type=int, default=0)
    parser.add_argument("--pad-bottom", type=int, default=10)
    parser.add_argument("--pad-left", type=int, default=0)
    parser.add_argument("--pad-right", type=int, default=0)
    parser.add_argument("--resize-factor", type=int, default=1)
    parser.add_argument("--output", default="outputs/gina_wav2lip_video_final.mp4")
    return parser.parse_args()


def resolve_project_path(path: str):
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = (PROJECT_DIR / resolved).resolve()
    return resolved


def main():
    args = parse_args()
    video_path = resolve_project_path(args.video)
    audio_path = resolve_project_path(args.audio)
    output_path = resolve_project_path(args.output)

    if not video_path.exists():
        raise SystemExit(f"Video/image not found: {video_path}")
    if not audio_path.exists():
        raise SystemExit(f"Audio not found: {audio_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = generate_wav2lip_file_video(
        video_or_image_path=str(video_path),
        audio_path=str(audio_path),
        config={
            "space_id": args.space_id,
            "api_name": args.api_name,
            "checkpoint": args.checkpoint,
            "pad_top": args.pad_top,
            "pad_bottom": args.pad_bottom,
            "pad_left": args.pad_left,
            "pad_right": args.pad_right,
            "resize_factor": args.resize_factor,
        },
        output_dir=str(output_path.parent),
        output_name=output_path.name,
    )

    if not result:
        raise SystemExit("Wav2Lip returned no result.")

    print(f"Generated Wav2Lip video: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

from src.lipsync import generate_musetalk_bbox_video  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Run a MuseTalk bbox-style Space once.")
    parser.add_argument("--video", required=True, help="Source video path")
    parser.add_argument("--audio", required=True, help="Driving audio path")
    parser.add_argument("--space-id", default="scratchyourbrain123/MuseTalk")
    parser.add_argument("--api-name", default="/inference")
    parser.add_argument("--bbox-shift", type=int, default=0)
    parser.add_argument("--video-payload", default="dict", choices=["dict", "path"])
    parser.add_argument("--output", default="outputs/gina_musetalk_bbox_final.mp4")
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
        raise SystemExit(f"Video not found: {video_path}")
    if not audio_path.exists():
        raise SystemExit(f"Audio not found: {audio_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = generate_musetalk_bbox_video(
        video_path=str(video_path),
        audio_path=str(audio_path),
        config={
            "space_id": args.space_id,
            "api_name": args.api_name,
            "bbox_shift": args.bbox_shift,
            "video_payload": args.video_payload,
        },
        output_dir=str(output_path.parent),
        output_name=output_path.name,
    )

    if not result:
        raise SystemExit("MuseTalk bbox Space returned no result.")

    print(f"Generated MuseTalk bbox video: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

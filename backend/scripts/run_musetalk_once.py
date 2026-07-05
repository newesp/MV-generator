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

from src.lipsync import generate_musetalk_video  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Run MuseTalk once with a source video and audio file.")
    parser.add_argument("--video", required=True, help="Source video path")
    parser.add_argument("--audio", required=True, help="Driving audio path")
    parser.add_argument("--space-id", default="trymonolith/MuseTalk")
    parser.add_argument("--api-name", default="/generate_lipsync_video")
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--quality", default="Medium", choices=["Low", "Medium", "High"])
    parser.add_argument("--output", default="outputs/gina_musetalk_final.mp4")
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
    result = generate_musetalk_video(
        video_path=str(video_path),
        audio_path=str(audio_path),
        config={
            "space_id": args.space_id,
            "api_name": args.api_name,
            "fps": args.fps,
            "quality": args.quality,
        },
        output_dir=str(output_path.parent),
        output_name=output_path.name,
    )

    if not result:
        raise SystemExit("MuseTalk returned no result.")

    print(f"Generated MuseTalk video: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

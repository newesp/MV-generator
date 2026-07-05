import argparse
import os
import sys
from pathlib import Path

from gradio_client import Client

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from src.lipsync import generate_lipsync_video  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect or test a Hugging Face lip-sync Space.")
    parser.add_argument("--space-id", required=True, help="Hugging Face Space ID, for example owner/space")
    parser.add_argument(
        "--provider",
        default="wav2lip_zerogpu_hf",
        choices=["sadtalker_hf", "wav2lip_zerogpu_hf", "liveportrait_hf"],
    )
    parser.add_argument("--api-name", help="Override Gradio API endpoint name")
    parser.add_argument("--image", help="Source portrait image for a real prediction test")
    parser.add_argument("--audio", help="Short driving audio clip for a real prediction test")
    parser.add_argument("--output-dir", default=str(BACKEND_DIR.parent / "outputs"))
    parser.add_argument("--predict", action="store_true", help="Run a prediction after printing API info")
    return parser.parse_args()


def main():
    args = parse_args()

    print(f"Connecting to {args.space_id}...")
    client = Client(args.space_id)

    print("\n--- Space API ---")
    print(client.view_api())

    if not args.predict:
        print("\nAPI inspection complete. Re-run with --predict --image ... --audio ... to test generation.")
        return 0

    if not args.image or not args.audio:
        raise SystemExit("--predict requires both --image and --audio")

    os.makedirs(args.output_dir, exist_ok=True)
    default_api_names = {
        "wav2lip_zerogpu_hf": "/run_inference",
        "liveportrait_hf": "/predict",
    }
    provider_config = {
        "provider": args.provider,
        "space_id": args.space_id,
        "api_name": args.api_name or default_api_names.get(args.provider),
        "fn_index": 0,
        "preprocess": "crop",
        "still_mode": True,
        "use_face_enhancer": False,
        "batch_size": 2,
        "face_model_resolution": "256",
        "pose_style": 0,
    }
    result = generate_lipsync_video(
        image_path=args.image,
        audio_path=args.audio,
        config=provider_config,
        output_dir=args.output_dir,
        segment_index=0,
    )

    if not result:
        raise SystemExit("Prediction failed or returned an unsupported format.")

    print(f"\nGenerated lip-sync video: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

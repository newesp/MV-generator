import argparse
import sys
from pathlib import Path

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from src.pipeline import run_pipeline  # noqa: E402


def load_config():
    config_path = BACKEND_DIR / "configs" / "config.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for key in ("inputs_dir", "outputs_dir"):
        configured_path = Path(config["paths"][key])
        if not configured_path.is_absolute():
            configured_path = BACKEND_DIR / configured_path
        config["paths"][key] = str(configured_path.resolve())

    return config


def parse_args():
    parser = argparse.ArgumentParser(description="Run the MV pipeline once from the command line.")
    parser.add_argument("audio", help="Path to the source audio file")
    parser.add_argument("--image", help="Optional exact source image to use for every segment")
    return parser.parse_args()


def main():
    args = parse_args()
    audio_path = Path(args.audio)
    if not audio_path.is_absolute():
        audio_path = (BACKEND_DIR.parent / audio_path).resolve()

    config = load_config()
    if args.image:
        image_path = Path(args.image)
        if not image_path.is_absolute():
            image_path = (BACKEND_DIR.parent / image_path).resolve()
        config.setdefault("visual", {})["preferred_image"] = str(image_path)

    result = run_pipeline(str(audio_path), config)
    if not result:
        raise SystemExit("Pipeline returned no result.")

    print(f"Generated MV: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

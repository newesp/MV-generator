from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mouth_tracking import (  # noqa: E402
    Rect,
    color_match_patch,
    ellipse_mask,
    mouth_rect_from_normalized_landmarks,
    smooth_rect,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Composite a LatentSync mouth layer back into a 16:9 base video using per-frame mouth landmarks."
    )
    parser.add_argument("--base-video", required=True, help="Original 16:9 base MP4.")
    parser.add_argument("--face-layer", required=True, help="LatentSync cropped face-layer MP4.")
    parser.add_argument("--audio", help="Optional song/audio file to mux into the output.")
    parser.add_argument("--output", required=True, help="Output MP4 path.")
    parser.add_argument("--max-seconds", type=float, default=30.0)
    parser.add_argument("--target-padding-x", type=float, default=0.25)
    parser.add_argument("--target-padding-y", type=float, default=0.45)
    parser.add_argument("--source-padding-x", type=float, default=0.20)
    parser.add_argument("--source-padding-y", type=float, default=0.35)
    parser.add_argument("--smooth", type=float, default=0.35, help="Current-frame weight for mouth box smoothing.")
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--mask-feather", type=float, default=1.6)
    parser.add_argument("--min-mouth-size", type=int, default=16)
    parser.add_argument("--preview-dir", help="Optional directory for debug frames.")
    parser.add_argument("--preview-every", type=int, default=120)
    parser.add_argument("--debug-overlay", action="store_true", help="Draw target/source boxes on preview frames.")
    return parser.parse_args()


def require_runtime_deps():
    try:
        import cv2  # noqa: PLC0415
        import mediapipe as mp  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
    except ImportError as exc:
        raise SystemExit(
            "This script needs opencv-python, mediapipe, and numpy. "
            "Run it on the RunPod LatentSync environment or install those packages locally."
        ) from exc
    return cv2, mp, np


def clamp_rect(rect: Rect, frame_width: int, frame_height: int) -> Rect:
    x = max(0, min(rect.x, frame_width - 1))
    y = max(0, min(rect.y, frame_height - 1))
    right = max(x + 1, min(rect.right, frame_width))
    bottom = max(y + 1, min(rect.bottom, frame_height))
    return Rect(x=x, y=y, width=right - x, height=bottom - y)


def detect_mouth_rect(
    cv2,
    face_mesh,
    frame_bgr,
    *,
    padding_x: float,
    padding_y: float,
    min_size: int,
) -> Rect | None:
    height, width = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = face_mesh.process(rgb)
    if not result.multi_face_landmarks:
        return None

    candidates: list[Rect] = []
    for face in result.multi_face_landmarks:
        try:
            rect = mouth_rect_from_normalized_landmarks(
                face.landmark,
                frame_width=width,
                frame_height=height,
                padding_x=padding_x,
                padding_y=padding_y,
                min_size=min_size,
            )
        except ValueError:
            continue
        if rect.is_valid():
            candidates.append(clamp_rect(rect, width, height))

    if not candidates:
        return None
    return max(candidates, key=lambda r: r.width * r.height)


def frame_at_time(capture, cv2, t_seconds: float):
    capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t_seconds * 1000.0))
    ok, frame = capture.read()
    if not ok:
        return None
    return frame


def mux_audio(ffmpeg_output: Path, silent_path: Path, audio_path: Path, max_seconds: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(silent_path),
            "-i",
            str(audio_path),
            "-t",
            str(max_seconds),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(ffmpeg_output),
        ],
        check=True,
    )


def main() -> int:
    args = parse_args()
    cv2, mp, np = require_runtime_deps()

    base_path = Path(args.base_video)
    face_path = Path(args.face_layer)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    preview_dir = Path(args.preview_dir) if args.preview_dir else None
    if preview_dir:
        preview_dir.mkdir(parents=True, exist_ok=True)

    base_cap = cv2.VideoCapture(str(base_path))
    face_cap = cv2.VideoCapture(str(face_path))
    if not base_cap.isOpened():
        raise SystemExit(f"Cannot open base video: {base_path}")
    if not face_cap.isOpened():
        raise SystemExit(f"Cannot open face layer: {face_path}")

    fps = base_cap.get(cv2.CAP_PROP_FPS) or 24.0
    width = int(base_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(base_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(min(base_cap.get(cv2.CAP_PROP_FRAME_COUNT) or fps * args.max_seconds, fps * args.max_seconds))

    silent_path = output_path if not args.audio else output_path.with_name(output_path.stem + "_silent.mp4")
    writer = cv2.VideoWriter(str(silent_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise SystemExit(f"Cannot write output video: {silent_path}")

    mp_face_mesh = mp.solutions.face_mesh
    base_mesh = mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=2, refine_landmarks=True)
    face_mesh = mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1, refine_landmarks=True)

    previous_target: Rect | None = None
    previous_source: Rect | None = None
    used_frames = 0
    skipped_frames = 0

    try:
        for frame_index in range(total_frames):
            ok, base_frame = base_cap.read()
            if not ok:
                break

            t_seconds = frame_index / fps
            face_frame = frame_at_time(face_cap, cv2, t_seconds)
            output_frame = base_frame.copy()

            target_rect = detect_mouth_rect(
                cv2,
                base_mesh,
                base_frame,
                padding_x=args.target_padding_x,
                padding_y=args.target_padding_y,
                min_size=args.min_mouth_size,
            )
            source_rect = None
            if face_frame is not None:
                source_rect = detect_mouth_rect(
                    cv2,
                    face_mesh,
                    face_frame,
                    padding_x=args.source_padding_x,
                    padding_y=args.source_padding_y,
                    min_size=args.min_mouth_size,
                )

            if target_rect and source_rect:
                target_rect = clamp_rect(smooth_rect(previous_target, target_rect, current_weight=args.smooth), width, height)
                source_rect = clamp_rect(
                    smooth_rect(previous_source, source_rect, current_weight=args.smooth),
                    face_frame.shape[1],
                    face_frame.shape[0],
                )
                previous_target = target_rect
                previous_source = source_rect

                source_patch = face_frame[source_rect.y : source_rect.bottom, source_rect.x : source_rect.right]
                target_roi = output_frame[target_rect.y : target_rect.bottom, target_rect.x : target_rect.right]

                if source_patch.size and target_roi.size:
                    resized_patch = cv2.resize(
                        source_patch,
                        (target_rect.width, target_rect.height),
                        interpolation=cv2.INTER_CUBIC,
                    ).astype(np.float32)
                    target_float = target_roi.astype(np.float32)
                    mask = ellipse_mask(target_rect.width, target_rect.height, feather=args.mask_feather)
                    mask = np.clip(mask * args.alpha, 0.0, 1.0)
                    matched_patch = color_match_patch(resized_patch, target_float, mask)
                    blended = target_float * (1.0 - mask[..., None]) + matched_patch * mask[..., None]
                    output_frame[target_rect.y : target_rect.bottom, target_rect.x : target_rect.right] = np.clip(
                        blended,
                        0,
                        255,
                    ).astype(np.uint8)
                    used_frames += 1
                else:
                    skipped_frames += 1
            else:
                skipped_frames += 1

            if preview_dir and (frame_index % max(1, args.preview_every) == 0):
                preview = output_frame.copy()
                if args.debug_overlay:
                    if target_rect:
                        cv2.rectangle(
                            preview,
                            (target_rect.x, target_rect.y),
                            (target_rect.right, target_rect.bottom),
                            (0, 255, 0),
                            2,
                        )
                    if source_rect:
                        cv2.putText(
                            preview,
                            f"src {source_rect.x},{source_rect.y},{source_rect.width},{source_rect.height}",
                            (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.8,
                            (0, 255, 255),
                            2,
                        )
                cv2.imwrite(str(preview_dir / f"frame_{frame_index:05d}.png"), preview)

            writer.write(output_frame)
    finally:
        base_mesh.close()
        face_mesh.close()
        base_cap.release()
        face_cap.release()
        writer.release()

    if args.audio:
        mux_audio(output_path, silent_path, Path(args.audio), args.max_seconds)

    print(f"frames_total={total_frames}")
    print(f"frames_composited={used_frames}")
    print(f"frames_skipped={skipped_frames}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

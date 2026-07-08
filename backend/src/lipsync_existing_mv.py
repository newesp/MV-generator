from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.merger import run_ffmpeg


class RangeValidationError(ValueError):
    pass


@dataclass(frozen=True)
class LipsyncRange:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "duration": self.duration}


@dataclass(frozen=True)
class MediaMetadata:
    duration: float
    width: int | None = None
    height: int | None = None
    fps: str | None = None
    sample_rate: int | None = None
    channels: int | None = None

    def to_dict(self) -> dict:
        return {
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
        }


@dataclass(frozen=True)
class PreparedLipsyncJob:
    job_id: str
    job_dir: Path
    source_video: Path
    metadata: MediaMetadata
    ranges: list[LipsyncRange]
    segment_video_paths: list[Path]
    segment_audio_paths: list[Path]
    runpod_bundle_dir: Path

    def artifacts(self) -> dict:
        return {
            "job_dir": str(self.job_dir),
            "source": str(self.source_video),
            "runpod_bundle": str(self.runpod_bundle_dir),
            "segments": [str(path) for path in self.segment_video_paths],
            "segment_audio": [str(path) for path in self.segment_audio_paths],
        }


def parse_lipsync_ranges(raw_ranges, duration: float) -> list[LipsyncRange]:
    if isinstance(raw_ranges, str):
        try:
            raw_ranges = json.loads(raw_ranges)
        except json.JSONDecodeError as exc:
            raise RangeValidationError("ranges must be valid JSON") from exc

    if not isinstance(raw_ranges, list) or not raw_ranges:
        raise RangeValidationError("ranges must contain at least one time range")

    ranges: list[LipsyncRange] = []
    for index, item in enumerate(raw_ranges, start=1):
        if not isinstance(item, dict):
            raise RangeValidationError(f"range {index} must be an object")
        try:
            start = float(item["start"])
            end = float(item["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RangeValidationError(f"range {index} must include numeric start and end") from exc
        if start < 0:
            raise RangeValidationError(f"range {index} start must be 0 or greater")
        if end <= start:
            raise RangeValidationError(f"range {index} end must be greater than start")
        if end > duration:
            raise RangeValidationError(f"range {index} end exceeds media duration")
        ranges.append(LipsyncRange(round(start, 3), round(end, 3)))

    ranges.sort(key=lambda item: item.start)
    previous_end = None
    for index, item in enumerate(ranges, start=1):
        if previous_end is not None and item.start < previous_end:
            raise RangeValidationError(f"range {index} overlaps a previous range")
        previous_end = item.end
    return ranges


def probe_media_metadata(video_path: Path) -> MediaMetadata:
    payload = _run_ffprobe_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,r_frame_rate,sample_rate,channels",
            "-of",
            "json",
            str(video_path),
        ]
    )
    duration = float(payload.get("format", {}).get("duration", 0))
    video_stream = _first_stream(payload.get("streams", []), "video")
    audio_stream = _first_stream(payload.get("streams", []), "audio")
    if duration <= 0:
        raise RuntimeError("Unable to read media duration")
    return MediaMetadata(
        duration=duration,
        width=video_stream.get("width"),
        height=video_stream.get("height"),
        fps=video_stream.get("r_frame_rate"),
        sample_rate=_safe_int(audio_stream.get("sample_rate")),
        channels=audio_stream.get("channels"),
    )


def prepare_lipsync_existing_mv_job(
    job_id: str,
    source_video: Path,
    ranges_json,
    outputs_dir: Path,
) -> PreparedLipsyncJob:
    metadata = probe_media_metadata(source_video)
    ranges = parse_lipsync_ranges(ranges_json, metadata.duration)
    job_dir = outputs_dir / job_id
    segment_dir = job_dir / "segments"
    audio_dir = job_dir / "audio"
    job_dir.mkdir(parents=True, exist_ok=True)
    segment_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    canonical_source = job_dir / "source.mp4"
    if source_video.resolve() != canonical_source.resolve():
        shutil.copy2(source_video, canonical_source)
    else:
        canonical_source = source_video

    segment_video_paths: list[Path] = []
    segment_audio_paths: list[Path] = []
    for index, item in enumerate(ranges, start=1):
        segment_video = segment_dir / f"range_{index:03d}_source.mp4"
        segment_audio = audio_dir / f"range_{index:03d}_audio.wav"
        _extract_video_segment(canonical_source, item.start, item.duration, segment_video, f"Extract target segment {index}")
        _extract_audio_segment(canonical_source, item.start, item.duration, segment_audio, f"Extract target audio {index}")
        segment_video_paths.append(segment_video)
        segment_audio_paths.append(segment_audio)

    bundle_dir = create_manual_runpod_bundle(
        job_id=job_id,
        job_dir=job_dir,
        source_video=canonical_source,
        ranges=ranges,
        segment_video_paths=segment_video_paths,
        segment_audio_paths=segment_audio_paths,
    )
    return PreparedLipsyncJob(
        job_id=job_id,
        job_dir=job_dir,
        source_video=canonical_source,
        metadata=metadata,
        ranges=ranges,
        segment_video_paths=segment_video_paths,
        segment_audio_paths=segment_audio_paths,
        runpod_bundle_dir=bundle_dir,
    )


def create_manual_runpod_bundle(
    job_id: str,
    job_dir: Path,
    source_video: Path,
    ranges: list[LipsyncRange],
    segment_video_paths: list[Path],
    segment_audio_paths: list[Path],
) -> Path:
    bundle_dir = job_dir / "runpod_manual_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "job_id": job_id,
        "source_video": str(source_video),
        "latentsync_root": "/workspace/LatentSync",
        "segments": [
            {
                "index": index,
                "range": item.to_dict(),
                "source": str(segment_video_paths[index - 1]),
                "audio": str(segment_audio_paths[index - 1]),
                "upload_name": segment_video_paths[index - 1].name,
                "audio_upload_name": segment_audio_paths[index - 1].name,
                "target_output": f"range_{index:03d}_processed.mp4",
            }
            for index, item in enumerate(ranges, start=1)
        ],
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (bundle_dir / "README.md").write_text(_manual_runpod_readme(manifest), encoding="utf-8")
    return bundle_dir


def stitch_processed_segments(
    source_video: Path,
    ranges: list[LipsyncRange],
    processed_segment_paths: list[Path],
    output_path: Path,
    duration: float,
) -> Path:
    if len(ranges) != len(processed_segment_paths):
        raise ValueError("processed_segment_paths must match ranges")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    source_fps = _source_fps(probe_media_metadata(source_video).fps)
    cursor = 0.0
    gap_index = 1
    for index, item in enumerate(ranges, start=1):
        if item.start > cursor:
            gap = output_path.parent / f"original_gap_{gap_index:03d}.mp4"
            _extract_video_segment(
                source_video,
                cursor,
                item.start - cursor,
                gap,
                f"Extract original gap {gap_index}",
                video_only=True,
                fps=source_fps,
            )
            parts.append(gap)
            gap_index += 1
        normalized = output_path.parent / f"processed_video_{index:03d}.mp4"
        _normalize_video_only_segment(
            processed_segment_paths[index - 1],
            normalized,
            f"Normalize processed segment {index}",
            fps=source_fps,
            duration=item.duration,
        )
        parts.append(normalized)
        cursor = item.end

    if cursor < duration:
        gap = output_path.parent / f"original_gap_{gap_index:03d}.mp4"
        _extract_video_segment(
            source_video,
            cursor,
            duration - cursor,
            gap,
            f"Extract original gap {gap_index}",
            video_only=True,
            fps=source_fps,
        )
        parts.append(gap)

    concat_file = output_path.parent / "stitch_parts.txt"
    concat_file.write_text(_concat_file_text(parts), encoding="utf-8")
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-i",
            str(source_video),
            "-t",
            f"{duration:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0?",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            source_fps,
            "-c:a",
            "copy",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        "Stitch lip-sync existing MV",
    )
    return output_path


def verify_final_video(video_path: Path, expected_duration: float, tolerance: float = 0.75) -> MediaMetadata:
    metadata = probe_media_metadata(video_path)
    if abs(metadata.duration - expected_duration) > tolerance:
        raise RuntimeError(
            f"Final video duration {metadata.duration:.3f}s differs from expected {expected_duration:.3f}s"
        )
    return metadata


def _extract_video_segment(
    source: Path,
    start: float,
    duration: float,
    output: Path,
    label: str,
    video_only: bool = False,
    fps: str | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
        "-map",
        "0:v:0",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
    ]
    if fps:
        cmd.extend(["-r", fps])
    if video_only:
        cmd.append("-an")
    else:
        cmd.extend(["-map", "0:a?", "-c:a", "aac"])
    cmd.extend(["-movflags", "+faststart", str(output)])
    run_ffmpeg(cmd, label)


def _normalize_video_only_segment(source: Path, output: Path, label: str, fps: str, duration: float) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            fps,
            "-an",
            "-movflags",
            "+faststart",
            str(output),
        ],
        label,
    )


def _extract_audio_segment(source: Path, start: float, duration: float, output: Path, label: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-vn",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output),
        ],
        label,
    )


def _manual_runpod_readme(manifest: dict) -> str:
    lines = [
        f"# Manual RunPod LatentSync Bundle for {manifest['job_id']}",
        "",
        "Run these steps in the RunPod Jupyter environment at `/workspace/LatentSync`.",
        "",
        "1. Upload each `range_###_source.mp4` segment to `/workspace/LatentSync/input_segments/`.",
        "2. Upload each `range_###_audio.wav` segment to `/workspace/LatentSync/input_audio/`.",
        "3. Run LatentSync once per segment.",
        "4. Download each processed file using the exact `range_###_processed.mp4` name.",
        "5. Upload processed files back to the local app, then resume stitching.",
        "",
        "```bash",
        "cd /workspace/LatentSync",
        "mkdir -p input_segments input_audio output_segments",
    ]
    for segment in manifest["segments"]:
        lines.extend(
            [
                "python -m scripts.inference \\",
                "  --unet_config_path configs/unet/stage2.yaml \\",
                f"  --video_path input_segments/{segment['upload_name']} \\",
                f"  --audio_path input_audio/{segment['audio_upload_name']} \\",
                "  --inference_ckpt_path checkpoints/latentsync_unet.pt \\",
                "  --inference_steps 10 \\",
                "  --guidance_scale 1.5 \\",
                "  --enable_deepcache \\",
                f"  --video_out_path output_segments/{segment['target_output']}",
            ]
        )
    lines.append("```")
    return "\n".join(lines) + "\n"


def _concat_file_text(parts: Iterable[Path]) -> str:
    return "".join(f"file '{str(path.resolve()).replace(chr(92), '/')}'\n" for path in parts)


def _source_fps(fps: str | None) -> str:
    if not fps or fps == "0/0":
        return "24"
    return fps


def _run_ffprobe_json(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return json.loads(result.stdout)


def _first_stream(streams: list[dict], codec_type: str) -> dict:
    return next((stream for stream in streams if stream.get("codec_type") == codec_type), {})


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

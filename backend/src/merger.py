import os
import subprocess


def run_ffmpeg(cmd: list[str], label: str):
    """Runs an FFmpeg command and raises a useful error when it fails."""
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        error_tail = result.stderr.strip()[-2000:]
        raise RuntimeError(f"{label} failed with exit code {result.returncode}: {error_tail}")
    return result

def get_audio_duration(audio_path: str) -> float:
    """Gets the duration of an audio file using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    try:
        output = subprocess.check_output(cmd).decode().strip()
        return float(output)
    except Exception as e:
        print(f"Error getting duration for {audio_path}: {e}")
        return 0.0

def create_static_video(image_path: str, duration: float, output_path: str):
    """Creates a static video from an image for a specific duration."""
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image_path,
        "-t", str(duration),
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
        "-r", "30",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ]
    run_ffmpeg(cmd, "Create static video")
    return output_path

def merge_clips_with_audio(video_clips: list, audio_path: str, output_path: str):
    """
    Concatenates video clips and multiplexes them with the original audio.
    """
    if not video_clips:
        raise ValueError("No video clips provided for merging.")

    # Create a concat demuxer file
    concat_file = os.path.join(os.path.dirname(output_path), "concat.txt")
    with open(concat_file, "w") as f:
        for clip in video_clips:
            # Escape path for ffmpeg concat
            safe_path = clip.replace("\\", "/")
            f.write(f"file '{safe_path}'\n")
    
    audio_duration = get_audio_duration(audio_path)

    # Merge using ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-i", audio_path,
        "-t", str(audio_duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", # End when the shortest stream ends
        "-movflags", "+faststart",
        output_path
    ]
    
    print(f"[Merger] Running FFmpeg to merge clips: {' '.join(cmd)}")
    run_ffmpeg(cmd, "Merge clips with audio")
    return output_path

def extract_audio_segment(audio_path: str, start: float, duration: float, output_path: str):
    """Extracts a segment of audio using FFmpeg."""
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-i", audio_path,
        "-t", str(duration), "-c:a", "aac",
        output_path
    ]
    run_ffmpeg(cmd, "Extract audio segment")
    return output_path

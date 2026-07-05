import os
from src.analyzer import analyze_audio
from src.generator import prepare_visual_assets
from src.lipsync import generate_lipsync_video
from src.merger import create_static_video, merge_clips_with_audio, get_audio_duration, extract_audio_segment


def build_beat_segments(timestamps: list[float], total_duration: float):
    segments = []
    start_times = []
    for i in range(len(timestamps)):
        start = timestamps[i]
        end = timestamps[i + 1] if i + 1 < len(timestamps) else total_duration
        if end > start:
            segments.append(end - start)
            start_times.append(start)
    return start_times, segments


def build_section_segments(total_duration: float, section_count: int):
    section_count = max(1, section_count)
    section_duration = total_duration / section_count
    start_times = [i * section_duration for i in range(section_count)]
    segments = []
    for i, start in enumerate(start_times):
        end = total_duration if i == section_count - 1 else (i + 1) * section_duration
        segments.append(end - start)
    return start_times, segments


def run_pipeline(audio_path: str, config: dict):
    """
    Main orchestration pipeline.
    """
    outputs_dir = config["paths"]["outputs_dir"]
    inputs_dir = config["paths"]["inputs_dir"]
    os.makedirs(outputs_dir, exist_ok=True)
    os.makedirs(inputs_dir, exist_ok=True)
    
    print(f"--- 1. Analyzing Audio ---")
    audio_config = config.get("audio", {})
    analysis = analyze_audio(
        audio_path,
        backtrack=audio_config.get("onset_backtrack", True),
        min_gap=float(audio_config.get("onset_min_gap", 0.5)),
    )
    timestamps = analysis["timestamps"]
    source_duration = get_audio_duration(audio_path)
    max_duration = audio_config.get("max_duration_seconds")
    total_duration = source_duration
    if max_duration:
        total_duration = min(source_duration, float(max_duration))
        print(f"Limiting MVP output to {total_duration:.2f}s of {source_duration:.2f}s audio.")
    timestamps = [t for t in timestamps if t < total_duration]
    if not timestamps or timestamps[0] > 0.1:
        timestamps.insert(0, 0.0)
    
    segment_mode = audio_config.get("segment_mode", "sections")
    if segment_mode == "beats":
        start_times, segments = build_beat_segments(timestamps, total_duration)
    else:
        section_count = int(audio_config.get("section_count", 8))
        start_times, segments = build_section_segments(total_duration, section_count)
            
    print(f"Using {segment_mode} mode with {len(segments)} segments.")
    
    print(f"--- 2. Preparing Visual Assets ---")
    try:
        visual_config = config.get("visual", {})
        assets = prepare_visual_assets(
            len(segments),
            inputs_dir,
            preferred_image=visual_config.get("preferred_image"),
        )
    except Exception as e:
        print(f"Asset Error: {e}")
        return None
        
    print(f"--- 3. Generating Clips ---")
    video_clips = []
    temp_audio_clips = []
    
    lipsync_config = config.get("lipsync", {})
    
    for i, (duration, image_path) in enumerate(zip(segments, assets)):
        print(f"Processing segment {i+1}/{len(segments)} (Duration: {duration:.2f}s)")
        
        start_time = start_times[i]
        temp_audio_path = os.path.join(outputs_dir, f"segment_{i:03d}.m4a")
        extract_audio_segment(audio_path, start_time, duration, temp_audio_path)
        temp_audio_clips.append(temp_audio_path)
        
        # Try generating lipsync video
        clip_path = generate_lipsync_video(image_path, temp_audio_path, lipsync_config, outputs_dir, i)
        
        # Fallback to static video if lipsync fails (e.g. rate limit, invalid space)
        if not clip_path:
            print(f"[Pipeline] Lip-sync failed for segment {i+1}. Falling back to static video.")
            temp_video_path = os.path.join(outputs_dir, f"segment_{i:03d}.mp4")
            clip_path = create_static_video(image_path, duration, temp_video_path)
            
        video_clips.append(clip_path)
        
    print(f"--- 4. Merging Video with Audio ---")
    final_output = os.path.join(outputs_dir, "final_mv.mp4")
    merge_clips_with_audio(video_clips, audio_path, final_output)
    
    # Clean up temp clips
    for temp_file in video_clips + temp_audio_clips:
        if temp_file != final_output and os.path.exists(temp_file):
            os.remove(temp_file)
            
    print(f"Pipeline finished! Output saved to: {final_output}")
    return final_output

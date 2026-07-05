import os
import urllib.request
import shutil
import traceback
from gradio_client import Client

try:
    from gradio_client import handle_file
except ImportError:
    handle_file = None


def _extract_candidate_paths(value):
    if isinstance(value, str):
        return [value]
    attr_candidates = []
    for attr in ("path", "url", "name"):
        if hasattr(value, attr):
            attr_value = getattr(value, attr)
            if attr_value:
                attr_candidates.extend(_extract_candidate_paths(attr_value))
    if attr_candidates:
        return attr_candidates
    if isinstance(value, dict):
        candidates = []
        for key in ("path", "url", "video", "value", "name"):
            if key in value:
                candidates.extend(_extract_candidate_paths(value[key]))
        for nested_value in value.values():
            if isinstance(nested_value, (dict, list, tuple)):
                candidates.extend(_extract_candidate_paths(nested_value))
        return candidates
    if isinstance(value, (list, tuple)):
        candidates = []
        for item in value:
            candidates.extend(_extract_candidate_paths(item))
        return candidates
    return []


def _save_result_file(result, out_file: str):
    candidates = _extract_candidate_paths(result)
    print(f"[LipSync] Result file candidates: {candidates}")
    for candidate in candidates:
        if candidate.startswith(("http://", "https://")):
            urllib.request.urlretrieve(candidate, out_file)
            return out_file
        if os.path.exists(candidate):
            shutil.copy(candidate, out_file)
            return out_file
    return None


def _file_arg(file_path: str):
    if handle_file:
        return handle_file(file_path)
    return file_path

def generate_sadtalker_video(image_path: str, audio_path: str, config: dict, output_dir: str, segment_index: int):
    """Calls a SadTalker Gradio Space: source image + audio -> talking-head video."""
    space_id = config["space_id"]
    print(f"[LipSync] Connecting to SadTalker HF Space: {space_id}")
    try:
        client = Client(space_id, download_files=False)
        result = client.predict(
            _file_arg(image_path),
            _file_arg(audio_path),
            config.get("preprocess", "crop"),
            bool(config.get("still_mode", True)),
            bool(config.get("use_face_enhancer", False)),
            int(config.get("batch_size", 2)),
            str(config.get("face_model_resolution", "256")),
            int(config.get("pose_style", 0)),
            fn_index=int(config.get("fn_index", 0)),
        )

        out_file = os.path.join(output_dir, f"segment_{segment_index:03d}_sync.mp4")
        saved_file = _save_result_file(result, out_file)
        if saved_file:
            return saved_file

        print(f"[LipSync] Unexpected SadTalker result format: {result}")
        return None

    except Exception as e:
        print(f"[LipSync Error] SadTalker failed for segment {segment_index}: {e}")
        traceback.print_exc()
        return None


def generate_wav2lip_zerogpu_video(image_path: str, audio_path: str, config: dict, output_dir: str, segment_index: int):
    """Calls a Wav2Lip ZeroGPU Gradio Space: source image + audio -> lip-sync video."""
    space_id = config["space_id"]
    api_name = config.get("api_name", "/run_inference")
    print(f"[LipSync] Connecting to Wav2Lip HF Space: {space_id}")
    try:
        client = Client(space_id, download_files=False)
        result = client.predict(
            _file_arg(image_path),
            _file_arg(audio_path),
            api_name=api_name,
        )

        out_file = os.path.join(output_dir, f"segment_{segment_index:03d}_sync.mp4")
        saved_file = _save_result_file(result, out_file)
        if saved_file:
            return saved_file

        print(f"[LipSync] Unexpected Wav2Lip result format: {result}")
        return None

    except Exception as e:
        print(f"[LipSync Error] Wav2Lip failed for segment {segment_index}: {e}")
        traceback.print_exc()
        return None


def generate_wav2lip_file_video(video_or_image_path: str, audio_path: str, config: dict, output_dir: str, output_name: str = "wav2lip_output.mp4"):
    """Calls a Wav2Lip Gradio Space that accepts either a source video or image plus audio."""
    space_id = config["space_id"]
    api_name = config.get("api_name", "/generate")
    print(f"[LipSync] Connecting to Wav2Lip video HF Space: {space_id}")
    try:
        client = Client(space_id, download_files=False)
        result = client.predict(
            _file_arg(video_or_image_path),
            _file_arg(audio_path),
            config.get("checkpoint", "wav2lip_gan"),
            int(config.get("pad_top", 0)),
            int(config.get("pad_bottom", 10)),
            int(config.get("pad_left", 0)),
            int(config.get("pad_right", 0)),
            int(config.get("resize_factor", 1)),
            api_name=api_name,
        )

        out_file = os.path.join(output_dir, output_name)
        saved_file = _save_result_file(result, out_file)
        if saved_file:
            return saved_file

        print(f"[LipSync] Unexpected Wav2Lip file result format: {result}")
        return None

    except Exception as e:
        print(f"[LipSync Error] Wav2Lip file provider failed: {e}")
        traceback.print_exc()
        return None


def generate_musetalk_video(video_path: str, audio_path: str, config: dict, output_dir: str, output_name: str = "musetalk_output.mp4"):
    """Calls a MuseTalk Gradio Space: source video + audio -> lip-sync video."""
    space_id = config["space_id"]
    api_name = config.get("api_name", "/generate_lipsync_video")
    print(f"[LipSync] Connecting to MuseTalk HF Space: {space_id}")
    try:
        client = Client(space_id)
        result = client.predict(
            _file_arg(audio_path),
            _file_arg(video_path),
            int(config.get("fps", 25)),
            config.get("quality", "Medium"),
            api_name=api_name,
        )

        out_file = os.path.join(output_dir, output_name)
        saved_file = _save_result_file(result, out_file)
        if saved_file:
            return saved_file

        print(f"[LipSync] Unexpected MuseTalk result format: {result}")
        return None

    except Exception as e:
        print(f"[LipSync Error] MuseTalk failed: {e}")
        traceback.print_exc()
        return None


def generate_musetalk_bbox_video(video_path: str, audio_path: str, config: dict, output_dir: str, output_name: str = "musetalk_bbox_output.mp4"):
    """Calls a MuseTalk Space that expects video, audio, and bbox_shift."""
    space_id = config["space_id"]
    api_name = config.get("api_name", "/inference")
    print(f"[LipSync] Connecting to MuseTalk bbox HF Space: {space_id}")
    try:
        client = Client(space_id)
        video_payload = {"video": _file_arg(video_path), "subtitles": None}
        if config.get("video_payload", "dict") == "path":
            video_payload = _file_arg(video_path)

        result = client.predict(
            video_payload,
            _file_arg(audio_path),
            int(config.get("bbox_shift", 0)),
            api_name=api_name,
        )

        out_file = os.path.join(output_dir, output_name)
        saved_file = _save_result_file(result, out_file)
        if saved_file:
            return saved_file

        print(f"[LipSync] Unexpected MuseTalk bbox result format: {result}")
        return None

    except Exception as e:
        print(f"[LipSync Error] MuseTalk bbox failed: {e}")
        traceback.print_exc()
        return None


def generate_liveportrait_video(image_path: str, audio_path: str, config: dict, output_dir: str, segment_index: int):
    """Legacy helper for experimental audio-driven LivePortrait-compatible Spaces."""
    space_id = config["space_id"]
    api_name = config.get("api_name", "/predict")
    print(f"[LipSync] Connecting to HF Space: {space_id}")
    try:
        client = Client(space_id)
        
        # Note: The exact arguments depend on the specific space's API. 
        # This is a generalized payload for a typical audio-driven space.
        result = client.predict(
            source_image=_file_arg(image_path),
            driving_audio=_file_arg(audio_path),
            api_name=api_name
        )
        
        # result is usually a path to the generated video on the local temp folder
        out_file = os.path.join(output_dir, f"segment_{segment_index:03d}_sync.mp4")
        
        saved_file = _save_result_file(result, out_file)
        if saved_file:
            return saved_file

        print(f"[LipSync] Unexpected result format: {result}")
        return None
            
    except Exception as e:
        print(f"[LipSync Error] Failed to generate lipsync for segment {segment_index}: {e}")
        traceback.print_exc()
        return None


def generate_lipsync_video(image_path: str, audio_path: str, config: dict, output_dir: str, segment_index: int):
    """
    Generates a lip-sync/talking-head video through the configured provider.

    Supported providers:
    - sadtalker_hf: source image + audio -> talking-head video
    - wav2lip_zerogpu_hf: source image + audio -> lip-sync video
    - liveportrait_hf: legacy experimental provider for compatible HF Spaces
    """
    provider = config.get("provider", "sadtalker_hf")
    if provider == "sadtalker_hf":
        return generate_sadtalker_video(image_path, audio_path, config, output_dir, segment_index)
    if provider == "wav2lip_zerogpu_hf":
        return generate_wav2lip_zerogpu_video(image_path, audio_path, config, output_dir, segment_index)
    if provider == "liveportrait_hf":
        return generate_liveportrait_video(image_path, audio_path, config, output_dir, segment_index)

    print(f"[LipSync] Unknown provider '{provider}'. Skipping lip-sync.")
    return None

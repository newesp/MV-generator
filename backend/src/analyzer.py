import librosa
import numpy as np

def analyze_audio(file_path: str, backtrack: bool = True, min_gap: float = 0.5):
    """
    Analyzes an audio file to extract BPM and significant onset timestamps (beats/drums).
    
    Args:
        file_path (str): Path to the audio file.
        backtrack (bool): If True, aligns onsets to the nearest local minimum of energy.
        min_gap (float): Minimum seconds between detected transition points.
        
    Returns:
        dict: A dictionary containing 'bpm' and 'timestamps' (list of floats).
    """
    print(f"Loading audio: {file_path}")
    y, sr = librosa.load(file_path, sr=None)
    
    print("Calculating tempo and beat frames...")
    # Get tempo and beat frames
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    
    # Calculate onset envelope for detecting strong hits/drums
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    
    # Get onset frames
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, backtrack=backtrack)
    
    # Convert frames to time
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    
    # For MVP, we can combine or just use onset times as they represent strong "hits"
    # To avoid too rapid cuts, we can filter onset times that are too close to each other
    filtered_timestamps = []
    
    for t in onset_times:
        if not filtered_timestamps or (t - filtered_timestamps[-1]) >= min_gap:
            filtered_timestamps.append(t)
            
    # Ensure 0.0 is the first timestamp
    if not filtered_timestamps or filtered_timestamps[0] > 0.1:
        filtered_timestamps.insert(0, 0.0)
        
    # Make sure we can handle scalar or array return from beat_track
    bpm_value = float(tempo[0]) if isinstance(tempo, np.ndarray) else float(tempo)
        
    return {
        "bpm": bpm_value,
        "timestamps": [float(t) for t in filtered_timestamps],
        "beat_times": [float(t) for t in beat_times]
    }

if __name__ == "__main__":
    # Test script if run directly
    import sys
    if len(sys.argv) > 1:
        res = analyze_audio(sys.argv[1])
        print(f"BPM: {res['bpm']}")
        print(f"Detected {len(res['timestamps'])} transitions.")

import os
import yaml
from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from src.job_store import JobStore
from src.lipsync_existing_mv import (
    RangeValidationError,
    parse_lipsync_ranges,
    prepare_lipsync_existing_mv_job,
    stitch_processed_segments,
    verify_final_video,
)
from src.pipeline import run_pipeline
from src.runpod_latentsync import RunPodLatentSyncProvider
import shutil
from pathlib import Path

app = FastAPI(title="MV Generator API")

# Allow CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_config():
    backend_dir = Path(__file__).resolve().parent
    config_path = backend_dir / "configs" / "config.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        loaded_config = yaml.safe_load(f)

    paths = loaded_config.setdefault("paths", {})
    for key in ("inputs_dir", "outputs_dir"):
        configured_path = Path(paths[key])
        if not configured_path.is_absolute():
            configured_path = backend_dir / configured_path
        paths[key] = str(configured_path.resolve())

    return loaded_config

config = load_config()
INPUTS_DIR = config["paths"]["inputs_dir"]
OUTPUTS_DIR = config["paths"]["outputs_dir"]

os.makedirs(INPUTS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# Simple state manager for MVP
generation_status = {"status": "idle", "message": "", "result": None}
job_store = JobStore()

def process_mv_task(audio_path: str):
    global generation_status
    generation_status = {"status": "running", "message": "Analyzing music and generating MV...", "result": None}
    
    try:
        result_path = run_pipeline(audio_path, config)
        if result_path and os.path.exists(result_path):
            generation_status = {"status": "completed", "message": "MV Generated successfully!", "result": result_path}
        else:
            generation_status = {"status": "failed", "message": "Pipeline returned no result.", "result": None}
    except Exception as e:
        generation_status = {"status": "failed", "message": str(e), "result": None}

def process_lipsync_existing_mv_task(job_id: str, source_path: Path, ranges_json: str):
    try:
        job_store.update_job(
            job_id,
            status="running",
            stage="prepare_local",
            progress=0.08,
            message="Preparing local video and audio segments.",
        )
        prepared = prepare_lipsync_existing_mv_job(
            job_id=job_id,
            source_video=source_path,
            ranges_json=ranges_json,
            outputs_dir=Path(OUTPUTS_DIR),
        )
        job_store.update_job(
            job_id,
            status="running",
            stage="runpod_auto",
            progress=0.6,
            message="Running LatentSync on RunPod.",
            metadata=prepared.metadata.to_dict(),
            ranges=[item.to_dict() for item in prepared.ranges],
            artifacts=prepared.artifacts(),
        )

        provider = RunPodLatentSyncProvider.from_env()

        def update_runpod_status(**changes):
            job_store.update_job(job_id, status="running", **changes)

        processed_paths = provider.process_prepared_job(prepared, status_callback=update_runpod_status)
        processed_segments = {str(index): str(path) for index, path in enumerate(processed_paths, start=1)}
        job_store.update_job(
            job_id,
            status="running",
            stage="stitch",
            progress=0.92,
            message="Stitching processed lip-sync segments back into the source MV.",
            artifacts={"processed_segments": processed_segments},
        )

        final_path = prepared.job_dir / "final.mp4"
        stitch_processed_segments(prepared.source_video, prepared.ranges, processed_paths, final_path, prepared.metadata.duration)
        verified = verify_final_video(final_path, prepared.metadata.duration)
        job_store.update_job(
            job_id,
            status="completed",
            stage="verified",
            progress=1.0,
            message="Lip-sync existing MV completed and verified.",
            verification=verified.to_dict(),
            artifacts={"final": str(final_path)},
        )
    except RangeValidationError as exc:
        job_store.update_job(
            job_id,
            status="failed",
            stage="validate_ranges",
            progress=1.0,
            message=str(exc),
        )
    except Exception as exc:
        job_store.update_job(
            job_id,
            status="failed",
            stage="runpod_auto",
            progress=1.0,
            message=str(exc),
        )

@app.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    filename = os.path.basename(file.filename)
    file_path = os.path.join(INPUTS_DIR, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": filename, "message": "Image uploaded."}

@app.post("/generate")
async def generate_mv(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    global generation_status
    if generation_status["status"] == "running":
        return JSONResponse(status_code=400, content={"message": "A generation task is already running."})
        
    filename = os.path.basename(file.filename)
    audio_path = os.path.join(INPUTS_DIR, filename)
    with open(audio_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    background_tasks.add_task(process_mv_task, audio_path)
    return {"message": "Generation started."}

@app.get("/status")
async def get_status():
    return generation_status

@app.post("/lipsync-existing-mv")
async def create_lipsync_existing_mv_job(
    file: UploadFile = File(...),
    ranges: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    job = job_store.create_job(
        "lipsync_existing_mv",
        message="Preparing automatic RunPod LatentSync job.",
    )
    job_id = job["job_id"]
    job_store.update_job(
        job_id,
        status="running",
        stage="queued_auto",
        progress=0.05,
        message="Queued automatic RunPod LatentSync processing.",
    )

    job_input_dir = Path(OUTPUTS_DIR) / job_id / "uploads"
    job_input_dir.mkdir(parents=True, exist_ok=True)
    source_path = job_input_dir / _safe_upload_name(file.filename, "source.mp4")
    with source_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    background_tasks.add_task(process_lipsync_existing_mv_task, job_id, source_path, ranges)
    return job_store.get_job(job_id)

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"message": "Job not found."})
    return job

@app.post("/jobs/{job_id}/processed-segments/{segment_index}")
async def upload_processed_segment(job_id: str, segment_index: int, file: UploadFile = File(...)):
    job = job_store.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"message": "Job not found."})
    ranges = job.get("ranges", [])
    if segment_index < 1 or segment_index > len(ranges):
        return JSONResponse(status_code=400, content={"message": "Segment index is outside the job range list."})

    job_dir = Path(job.get("artifacts", {}).get("job_dir", Path(OUTPUTS_DIR) / job_id))
    processed_dir = job_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_path = processed_dir / f"range_{segment_index:03d}_processed.mp4"
    with processed_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    processed_segments = dict(job.get("artifacts", {}).get("processed_segments", {}))
    processed_segments[str(segment_index)] = str(processed_path)
    return job_store.update_job(
        job_id,
        status="waiting_manual",
        stage="collect_processed_segments",
        progress=0.7 + (0.2 * len(processed_segments) / max(1, len(ranges))),
        message=f"Received processed segment {segment_index} of {len(ranges)}.",
        artifacts={"processed_segments": processed_segments},
    )

@app.post("/jobs/{job_id}/resume-stitch")
async def resume_lipsync_existing_mv_stitch(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"message": "Job not found."})
    if job.get("workflow") != "lipsync_existing_mv":
        return JSONResponse(status_code=400, content={"message": "Job is not a lip-sync existing MV job."})

    try:
        artifacts = job.get("artifacts", {})
        metadata = job.get("metadata", {})
        duration = float(metadata["duration"])
        ranges = parse_lipsync_ranges(job.get("ranges", []), duration)
        job_dir = Path(artifacts.get("job_dir", Path(OUTPUTS_DIR) / job_id))
        source = Path(artifacts["source"])
        processed_paths = _processed_paths(job_dir, ranges)
        missing = [str(path) for path in processed_paths if not path.exists()]
        if missing:
            return JSONResponse(
                status_code=400,
                content={"message": "Missing processed segment artifacts.", "missing": missing},
            )

        job_store.update_job(
            job_id,
            status="running",
            stage="stitch",
            progress=0.92,
            message="Stitching processed lip-sync segments back into the source MV.",
        )
        final_path = job_dir / "final.mp4"
        stitch_processed_segments(source, ranges, processed_paths, final_path, duration)
        verified = verify_final_video(final_path, duration)
        return job_store.update_job(
            job_id,
            status="completed",
            stage="verified",
            progress=1.0,
            message="Lip-sync existing MV completed and verified.",
            verification=verified.to_dict(),
            artifacts={"final": str(final_path)},
        )
    except Exception as exc:
        failed = job_store.update_job(
            job_id,
            status="failed",
            stage="stitch",
            progress=1.0,
            message=str(exc),
        )
        return JSONResponse(status_code=500, content=failed)

@app.get("/jobs/{job_id}/download/final")
async def download_lipsync_existing_mv_result(job_id: str):
    job = job_store.get_job(job_id)
    final_path = job.get("artifacts", {}).get("final") if job else None
    if job and job.get("status") == "completed" and final_path and os.path.exists(final_path):
        return FileResponse(final_path, media_type="video/mp4", filename=f"{job_id}_lipsync_existing_mv.mp4")
    return JSONResponse(status_code=404, content={"message": "No completed final video found."})

@app.get("/download")
async def download_result():
    if generation_status["status"] == "completed" and generation_status["result"]:
        return FileResponse(generation_status["result"], media_type="video/mp4", filename="final_mv.mp4")
    return JSONResponse(status_code=404, content={"message": "No generated file found."})

def _safe_upload_name(filename: str | None, fallback: str) -> str:
    candidate = os.path.basename(filename or fallback)
    return candidate or fallback

def _processed_paths(job_dir: Path, ranges: list) -> list[Path]:
    return [job_dir / "processed" / f"range_{index:03d}_processed.mp4" for index, _ in enumerate(ranges, start=1)]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

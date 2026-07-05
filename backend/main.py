import os
import yaml
from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from src.pipeline import run_pipeline
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

@app.get("/download")
async def download_result():
    if generation_status["status"] == "completed" and generation_status["result"]:
        return FileResponse(generation_status["result"], media_type="video/mp4", filename="final_mv.mp4")
    return JSONResponse(status_code=404, content={"message": "No generated file found."})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

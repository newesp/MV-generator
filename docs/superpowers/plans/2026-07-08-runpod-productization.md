# RunPod Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the validated LatentSync MVP into a productizable provider that can run quality checks now and later evolve into RunPod API auto-start/stop and Serverless.

**Architecture:** Keep the existing `lipsync_existing_mv` workflow and isolate remote execution behind provider classes. First make the current Jupyter provider reproducible on a paid A40 Pod, then add a RunPod API lifecycle provider with persistent job state, and finally replace Jupyter execution with a Serverless worker contract.

**Tech Stack:** FastAPI, Python, FFmpeg, React/Vite, RunPod, LatentSync, unittest, Node test runner.

## Global Constraints

- Do not restart provider/model search. LatentSync is the current validated model.
- Do not process the unstable `4-6s` collage section for the first paid rerun; process only `6-13s`.
- Use `configs/unet/stage2.yaml`, `10` inference steps, `guidance_scale=1.5`, and `--enable_deepcache`.
- Segment audio must be WAV `pcm_s16le`, `16000 Hz`, mono.
- Preserve the original full-MV audio track in the final stitch.
- Do not deploy paid RunPod resources, add funds, or enable auto-pay without explicit user approval.
- Do not commit `inputs/*`, `outputs/*`, tokens, Jupyter proxy URLs, or generated debug media.

---

## File Structure

- Modify `backend/src/runpod_latentsync.py`: Keep the Jupyter provider, add clearer bootstrap checks, and later split API lifecycle code into a new module.
- Create `backend/src/runpod_lifecycle.py`: Own RunPod API Pod start/stop/status operations.
- Create `backend/src/persistent_job_store.py`: Replace the in-memory job store with a JSON or SQLite-backed MVP store.
- Modify `backend/main.py`: Wire provider choice, queue state, and persistent job status.
- Create `backend/scripts/run_lipsync_existing_mv_e2e.py`: Reproducible local command for the known `6-13s` E2E.
- Create `backend/scripts/bootstrap_latentsync_runpod.py`: Script that verifies or installs `/workspace/LatentSync` on a fresh Jupyter Pod.
- Modify `frontend/src/App.jsx`: Display provider errors and queue state without exposing Jupyter details.
- Test `tests/test_runpod_latentsync.py`: Jupyter provider recipe and connection checks.
- Test `tests/test_runpod_lifecycle.py`: RunPod API request/response behavior using mocked HTTP.
- Test `tests/test_persistent_job_store.py`: Job persistence and restart behavior.
- Test `tests/test_lipsync_api.py`: API status transitions and failure messages.

## Task 1: Freeze Known-Good MVP Behavior

**Files:**
- Modify: `tests/test_runpod_latentsync.py`
- Modify: `tests/test_lipsync_existing_mv.py`
- Modify: `IMPLEMENTATION_HANDOFF_2026-07-08.md`

**Interfaces:**
- Consumes: `build_latentsync_command(video_path: str, audio_path: str, output_path: str) -> list[str]`
- Produces: Regression coverage that prevents recipe drift.

- [ ] **Step 1: Run current regression tests**

Run:

```powershell
backend\venv\Scripts\python.exe -m unittest tests.test_runpod_latentsync tests.test_lipsync_existing_mv -v
```

Expected: all tests pass.

- [ ] **Step 2: Confirm recipe assertions exist**

Verify tests assert:

```text
configs/unet/stage2.yaml
--inference_steps 10
--guidance_scale 1.5
--enable_deepcache
no stage2_512.yaml
audio suffix .wav
pcm_s16le
-ar 16000
-ac 1
final stitch uses -c:a copy
concat paths are absolute
```

- [ ] **Step 3: Commit only docs/tests if new assertions were needed**

Run:

```powershell
git status --short
git add tests/test_runpod_latentsync.py tests/test_lipsync_existing_mv.py IMPLEMENTATION_HANDOFF_2026-07-08.md
git commit -m "docs: freeze latentsync mvp handoff"
```

Expected: commit succeeds. Skip commit if the user does not want commits yet.

## Task 2: Add Reproducible E2E Script

**Files:**
- Create: `backend/scripts/run_lipsync_existing_mv_e2e.py`
- Test: `tests/test_lipsync_api.py`

**Interfaces:**
- Consumes: `prepare_lipsync_existing_mv_job`, `RunPodLatentSyncProvider.from_env`, `stitch_processed_segments`, `verify_final_video`
- Produces: `python backend/scripts/run_lipsync_existing_mv_e2e.py --source inputs/Gina-MV.mp4 --start 6 --end 13`

- [ ] **Step 1: Write test for CLI argument parsing**

Add a test that imports the script module and calls a parser function:

```python
def test_parse_e2e_args_defaults_to_outputs_dir():
    args = parse_args(["--source", "inputs/Gina-MV.mp4", "--start", "6", "--end", "13"])
    assert args.source == Path("inputs/Gina-MV.mp4")
    assert args.start == 6.0
    assert args.end == 13.0
    assert args.outputs_dir == Path("outputs")
```

- [ ] **Step 2: Implement the parser**

Create `backend/scripts/run_lipsync_existing_mv_e2e.py` with:

```python
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from src.lipsync_existing_mv import prepare_lipsync_existing_mv_job, stitch_processed_segments, verify_final_video
from src.runpod_latentsync import RunPodLatentSyncProvider


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--outputs-dir", type=Path, default=Path("outputs"))
    return parser.parse_args(argv)
```

- [ ] **Step 3: Implement main**

Add:

```python
def main(argv=None) -> int:
    args = parse_args(argv)
    job_id = "runpod_e2e_" + uuid.uuid4().hex[:8]
    ranges = json.dumps([{"start": args.start, "end": args.end}])
    prepared = prepare_lipsync_existing_mv_job(job_id, args.source, ranges, args.outputs_dir)
    provider = RunPodLatentSyncProvider.from_env()
    processed = provider.process_prepared_job(prepared, status_callback=lambda **kw: print(kw, flush=True))
    final = prepared.job_dir / "final_runpod_e2e.mp4"
    stitch_processed_segments(prepared.source_video, prepared.ranges, processed, final, prepared.metadata.duration)
    verified = verify_final_video(final, prepared.metadata.duration)
    print(f"FINAL={final}")
    print(f"VERIFY={verified.to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run parser test**

Run:

```powershell
backend\venv\Scripts\python.exe -m unittest tests.test_lipsync_api -v
```

Expected: pass.

## Task 3: Add LatentSync Pod Bootstrap Check

**Files:**
- Create: `backend/scripts/bootstrap_latentsync_runpod.py`
- Modify: `backend/src/runpod_latentsync.py`
- Test: `tests/test_runpod_latentsync.py`

**Interfaces:**
- Consumes: Jupyter Contents API and kernel execution through `RunPodLatentSyncProvider`
- Produces: A deterministic preflight that says whether `/workspace/LatentSync` and checkpoints exist.

- [ ] **Step 1: Add provider method test**

Test expected missing-root error:

```python
def test_resolve_latentsync_root_reports_checked_paths():
    provider = RunPodLatentSyncProvider(RunPodLatentSyncSettings("https://example.test", "secret"))
    provider.session = _FakeSession(get_responses={})
    with self.assertRaisesRegex(RuntimeError, "workspace/LatentSync"):
        provider.resolve_latentsync_contents_root()
```

- [ ] **Step 2: Add checkpoint preflight**

Add method:

```python
def check_required_files(self) -> None:
    for remote_path in (
        f"{self.settings.latentsync_root}/configs/unet/stage2.yaml",
        f"{self.settings.latentsync_root}/checkpoints/latentsync_unet.pt",
    ):
        response = self.session.get(self._contents_url(remote_path), params={"content": 0}, timeout=30)
        self._raise_for_response(response, f"Check remote file {remote_path}")
```

- [ ] **Step 3: Call preflight before upload**

In `process_prepared_job`, after `resolve_latentsync_contents_root()`, call:

```python
self.check_required_files()
```

- [ ] **Step 4: Run provider tests**

Run:

```powershell
backend\venv\Scripts\python.exe -m unittest tests.test_runpod_latentsync -v
```

Expected: pass.

## Task 4: Paid A40 Quality Rerun

**Files:**
- No code file changes required unless preflight exposes a missing bootstrap.
- Generated outputs stay under `outputs/` and remain uncommitted.

**Interfaces:**
- Consumes: `backend/scripts/run_lipsync_existing_mv_e2e.py`
- Produces: `outputs/<job_id>/final_runpod_e2e.mp4`

- [ ] **Step 1: Get explicit approval**

Required user message:

```text
I approve deploying 1x A40 and running the 6-13s LatentSync E2E test.
```

- [ ] **Step 2: Deploy A40 only after approval and sufficient credit**

Use:

```text
Runpod Pytorch 2.8.0
1x A40
Jupyter enabled
```

Expected: RunPod opens a live `https://<pod>-8888.proxy.runpod.net/lab` URL.

- [ ] **Step 3: Set local env vars**

Run in the same terminal session used for E2E:

```powershell
$env:RUNPOD_JUPYTER_BASE_URL = "https://<pod>-8888.proxy.runpod.net"
$env:RUNPOD_JUPYTER_TOKEN = "<token>"
$env:RUNPOD_LATENTSYNC_ROOT = "/workspace/LatentSync"
$env:RUNPOD_LATENTSYNC_TIMEOUT_SECONDS = "1800"
```

- [ ] **Step 4: Run only stable range**

Run:

```powershell
backend\venv\Scripts\python.exe backend\scripts\run_lipsync_existing_mv_e2e.py --source inputs\Gina-MV.mp4 --start 6 --end 13
```

Expected:

```text
FINAL=outputs/<job_id>/final_runpod_e2e.mp4
VERIFY={'duration': about 28.67, 'width': 1280, 'height': 720, ...}
```

- [ ] **Step 5: Visual QA**

Extract frames:

```powershell
ffmpeg -y -ss 5.000 -i outputs\<job_id>\final_runpod_e2e.mp4 -frames:v 1 outputs\<job_id>\frame_05.png
ffmpeg -y -ss 8.500 -i outputs\<job_id>\final_runpod_e2e.mp4 -frames:v 1 outputs\<job_id>\frame_085.png
ffmpeg -y -ss 14.000 -i outputs\<job_id>\final_runpod_e2e.mp4 -frames:v 1 outputs\<job_id>\frame_14.png
```

Expected:

```text
5s: original unstable collage section remains original
8.5s: processed single-face section shows visible lip motion without neck paste artifacts
14s: original section resumes cleanly
```

## Task 5: Persistent Job Store

**Files:**
- Create: `backend/src/persistent_job_store.py`
- Modify: `backend/main.py`
- Test: `tests/test_persistent_job_store.py`

**Interfaces:**
- Consumes: current `JobStore` dictionary shape
- Produces: `PersistentJobStore(path: Path)` with `create_job`, `get_job`, `update_job`

- [ ] **Step 1: Write persistence test**

```python
def test_job_store_survives_restart(tmp_path):
    path = tmp_path / "jobs.json"
    first = PersistentJobStore(path)
    job = first.create_job("lipsync_existing_mv", message="queued")
    first.update_job(job["job_id"], status="running", stage="runpod")

    second = PersistentJobStore(path)
    restored = second.get_job(job["job_id"])

    assert restored["status"] == "running"
    assert restored["stage"] == "runpod"
```

- [ ] **Step 2: Implement file-backed store**

Use atomic replace:

```python
tmp_path = self.path.with_suffix(".tmp")
tmp_path.write_text(json.dumps(self.jobs, indent=2), encoding="utf-8")
tmp_path.replace(self.path)
```

- [ ] **Step 3: Wire in backend**

Replace:

```python
job_store = JobStore()
```

with:

```python
job_store = PersistentJobStore(Path(OUTPUTS_DIR) / "jobs.json")
```

- [ ] **Step 4: Run tests**

```powershell
backend\venv\Scripts\python.exe -m unittest tests.test_persistent_job_store tests.test_lipsync_api -v
```

Expected: pass.

## Task 6: RunPod API Lifecycle Provider

**Files:**
- Create: `backend/src/runpod_lifecycle.py`
- Modify: `backend/src/runpod_latentsync.py`
- Test: `tests/test_runpod_lifecycle.py`

**Interfaces:**
- Consumes: RunPod API token from `RUNPOD_API_KEY`
- Produces: `RunPodLifecycle.ensure_pod() -> RunPodPodConnection`

- [ ] **Step 1: Define dataclasses**

```python
@dataclass(frozen=True)
class RunPodPodConnection:
    pod_id: str
    jupyter_base_url: str
    jupyter_token: str
```

- [ ] **Step 2: Test no-key failure**

```python
@patch.dict(os.environ, {}, clear=True)
def test_lifecycle_requires_api_key():
    with self.assertRaisesRegex(RuntimeError, "RUNPOD_API_KEY"):
        RunPodLifecycle.from_env()
```

- [ ] **Step 3: Implement environment settings**

Required env vars:

```text
RUNPOD_API_KEY
RUNPOD_TEMPLATE_ID
RUNPOD_GPU_TYPE=A40
RUNPOD_IDLE_STOP_SECONDS=600
```

- [ ] **Step 4: Implement mocked API methods**

Create methods with mocked tests first:

```python
list_pods()
start_pod(pod_id)
create_pod()
stop_pod(pod_id)
wait_for_jupyter(pod_id)
```

- [ ] **Step 5: Do not call real RunPod API in unit tests**

All tests must use mocked `requests.Session`.

## Task 7: Queue and Auto-Stop Policy

**Files:**
- Create: `backend/src/job_queue.py`
- Modify: `backend/main.py`
- Test: `tests/test_job_queue.py`

**Interfaces:**
- Consumes: `PersistentJobStore`
- Produces: serial job runner with explicit states: `queued`, `preparing`, `remote_running`, `stitching`, `completed`, `failed`

- [ ] **Step 1: Add queue state test**

```python
def test_queue_runs_one_job_at_a_time():
    queue = JobQueue()
    queue.enqueue("job-1")
    queue.enqueue("job-2")
    assert queue.next_job() == "job-1"
    assert queue.next_job() == "job-2"
```

- [ ] **Step 2: Implement serial queue**

Keep it simple for MVP: one worker thread, no Redis yet.

- [ ] **Step 3: Add idle-stop hook**

After the queue becomes empty, call lifecycle stop only after:

```text
RUNPOD_IDLE_STOP_SECONDS
```

- [ ] **Step 4: Surface queue state in UI**

Show:

```text
Queued
Preparing local segments
Starting RunPod
Running LatentSync
Stitching final MV
Completed
Failed
```

## Task 8: Serverless Endpoint Design Gate

**Files:**
- Create: `docs/RUNPOD_SERVERLESS_DESIGN.md`

**Interfaces:**
- Consumes: validated A40 quality rerun
- Produces: decision record for Docker image and endpoint contract

- [ ] **Step 1: Document endpoint request**

```json
{
  "job_id": "uuid",
  "video_url": "https://object-store/source.mp4",
  "audio_url": "https://object-store/range_001_audio.wav",
  "range": {"start": 6.0, "end": 13.0},
  "recipe": {
    "unet_config_path": "configs/unet/stage2.yaml",
    "inference_steps": 10,
    "guidance_scale": 1.5,
    "enable_deepcache": true
  }
}
```

- [ ] **Step 2: Document endpoint response**

```json
{
  "job_id": "uuid",
  "status": "completed",
  "processed_video_url": "https://object-store/range_001_processed.mp4",
  "duration": 7.0
}
```

- [ ] **Step 3: Add go/no-go checklist**

Require:

```text
LatentSync quality accepted by user
single segment E2E stable
multi-range local stitch stable
object storage decision made
expected cost per 30s segment estimated
```

## Self-Review Checklist

- [ ] The plan preserves the known-good LatentSync recipe.
- [ ] The plan prevents reprocessing the unstable `4-6s` section during the next paid rerun.
- [ ] The plan keeps paid RunPod actions behind explicit user approval.
- [ ] The plan moves from manual Jupyter to API lifecycle before Serverless.
- [ ] The plan avoids committing generated media or secrets.


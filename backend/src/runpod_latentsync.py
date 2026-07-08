from __future__ import annotations

import asyncio
import base64
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import requests
import websockets


DEFAULT_LATENTSYNC_ROOT = "/workspace/LatentSync"
DEFAULT_UNET_CONFIG = "configs/unet/stage2.yaml"
DEFAULT_CHECKPOINT = "checkpoints/latentsync_unet.pt"
DEFAULT_INFERENCE_STEPS = 10
DEFAULT_GUIDANCE_SCALE = 1.5


@dataclass(frozen=True)
class RunPodLatentSyncSettings:
    base_url: str
    token: str
    latentsync_root: str = DEFAULT_LATENTSYNC_ROOT
    timeout_seconds: int = 1800

    @classmethod
    def from_env(cls) -> "RunPodLatentSyncSettings":
        base_url = os.getenv("RUNPOD_JUPYTER_BASE_URL", "").strip().rstrip("/")
        token = os.getenv("RUNPOD_JUPYTER_TOKEN", "").strip()
        if not base_url:
            raise RuntimeError("RUNPOD_JUPYTER_BASE_URL is required for automatic RunPod LatentSync.")
        if not token:
            raise RuntimeError("RUNPOD_JUPYTER_TOKEN is required for automatic RunPod LatentSync.")
        return cls(
            base_url=base_url,
            token=token,
            latentsync_root=os.getenv("RUNPOD_LATENTSYNC_ROOT", DEFAULT_LATENTSYNC_ROOT).strip()
            or DEFAULT_LATENTSYNC_ROOT,
            timeout_seconds=int(os.getenv("RUNPOD_LATENTSYNC_TIMEOUT_SECONDS", "1800")),
        )


def build_latentsync_command(
    *,
    video_path: str,
    audio_path: str,
    output_path: str,
) -> list[str]:
    return [
        "python3",
        "-m",
        "scripts.inference",
        "--unet_config_path",
        DEFAULT_UNET_CONFIG,
        "--inference_ckpt_path",
        DEFAULT_CHECKPOINT,
        "--inference_steps",
        str(DEFAULT_INFERENCE_STEPS),
        "--guidance_scale",
        str(DEFAULT_GUIDANCE_SCALE),
        "--enable_deepcache",
        "--video_path",
        video_path,
        "--audio_path",
        audio_path,
        "--video_out_path",
        output_path,
    ]


class RunPodLatentSyncProvider:
    def __init__(self, settings: RunPodLatentSyncSettings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"token {settings.token}"})
        self._latentsync_contents_path: str | None = None

    @classmethod
    def from_env(cls) -> "RunPodLatentSyncProvider":
        return cls(RunPodLatentSyncSettings.from_env())

    def process_prepared_job(self, prepared_job, status_callback=None) -> list[Path]:
        self.check_connection()
        self.resolve_latentsync_contents_root()
        processed_dir = prepared_job.job_dir / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        remote_job = _safe_remote_name(prepared_job.job_id)
        processed_paths: list[Path] = []

        for index, (segment_path, audio_path) in enumerate(
            zip(prepared_job.segment_video_paths, prepared_job.segment_audio_paths),
            start=1,
        ):
            if status_callback:
                status_callback(
                    stage="runpod_upload",
                    progress=0.62 + index * 0.03,
                    message=f"Uploading segment {index} of {len(prepared_job.ranges)} to RunPod.",
                )

            remote_segment = f"{self.settings.latentsync_root}/input_segments/{remote_job}/{segment_path.name}"
            remote_audio = f"{self.settings.latentsync_root}/input_audio/{remote_job}/{audio_path.name}"
            remote_output = f"{self.settings.latentsync_root}/output_segments/{remote_job}/range_{index:03d}_processed.mp4"
            self.upload_file(segment_path, remote_segment)
            self.upload_file(audio_path, remote_audio)

            if status_callback:
                status_callback(
                    stage="runpod_latentsync",
                    progress=0.68 + index * 0.08,
                    message=f"Running LatentSync segment {index} of {len(prepared_job.ranges)} on RunPod.",
                )

            command = build_latentsync_command(
                video_path=_relative_to_latentsync(remote_segment, self.settings.latentsync_root),
                audio_path=_relative_to_latentsync(remote_audio, self.settings.latentsync_root),
                output_path=_relative_to_latentsync(remote_output, self.settings.latentsync_root),
            )
            self.execute_latentsync(command)

            local_output = processed_dir / f"range_{index:03d}_processed.mp4"
            self.download_file(remote_output, local_output)
            processed_paths.append(local_output)

        return processed_paths

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        self.ensure_remote_directory(_remote_parent(remote_path))
        payload = {
            "type": "file",
            "format": "base64",
            "content": base64.b64encode(local_path.read_bytes()).decode("ascii"),
        }
        response = self.session.put(self._contents_url(remote_path), json=payload, timeout=120)
        self._raise_for_response(response, f"Upload {local_path.name}")

    def download_file(self, remote_path: str, local_path: Path) -> None:
        response = self.session.get(self._contents_url(remote_path), params={"content": 1}, timeout=120)
        self._raise_for_response(response, f"Download {remote_path}")
        payload = response.json()
        if payload.get("format") != "base64":
            raise RuntimeError(f"Unexpected Jupyter content format for {remote_path}: {payload.get('format')}")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(base64.b64decode(payload["content"]))

    def ensure_remote_directory(self, remote_dir: str) -> None:
        parts = self.contents_path(remote_dir).split("/")
        current: list[str] = []
        for part in parts:
            if not part:
                continue
            current.append(part)
            path = "/".join(current)
            existing = self.session.get(
                f"{self.settings.base_url}/api/contents/{quote(path, safe='/')}",
                params={"content": 0},
                timeout=30,
            )
            if existing.ok:
                if existing.json().get("type") != "directory":
                    raise RuntimeError(f"Remote path exists but is not a directory: {path}")
                continue
            if existing.status_code != 404:
                self._raise_for_response(existing, f"Check remote directory {path}")
            response = self.session.put(
                f"{self.settings.base_url}/api/contents/{quote(path, safe='/')}",
                json={"type": "directory"},
                timeout=30,
            )
            if response.status_code not in (200, 201):
                self._raise_for_response(response, f"Create remote directory {path}")

    def execute_latentsync(self, command: list[str]) -> str:
        code = _execution_code(self.settings.latentsync_root, command)
        return asyncio.run(self._execute_python(code))

    def check_connection(self) -> None:
        response = self.session.get(f"{self.settings.base_url}/api/kernelspecs", timeout=30)
        if response.ok:
            return
        raise RuntimeError(
            "RunPod Jupyter API is not reachable. Check that the Pod is running and "
            "RUNPOD_JUPYTER_BASE_URL points to the current 8888 proxy URL."
        )

    def resolve_latentsync_contents_root(self) -> str:
        if self._latentsync_contents_path:
            return self._latentsync_contents_path

        checked: list[str] = []
        for candidate in _contents_path_candidates(self.settings.latentsync_root):
            checked.append(candidate)
            response = self.session.get(
                f"{self.settings.base_url}/api/contents/{quote(candidate, safe='/')}",
                params={"content": 0},
                timeout=30,
            )
            if not response.ok:
                continue
            if response.json().get("type") != "directory":
                raise RuntimeError(f"Remote LatentSync root exists but is not a directory: {candidate}")
            self._latentsync_contents_path = candidate
            return candidate

        raise RuntimeError(
            "RunPod LatentSync root is not reachable via Jupyter Contents API. "
            f"Checked: {', '.join(checked)}"
        )

    def contents_path(self, remote_path: str) -> str:
        remote_normalized = _normalize_remote_path(remote_path)
        root_normalized = _normalize_remote_path(self.settings.latentsync_root)
        contents_root = self.resolve_latentsync_contents_root()
        if remote_normalized == root_normalized:
            return contents_root
        if remote_normalized.startswith(root_normalized + "/"):
            return contents_root + remote_normalized[len(root_normalized) :]
        return remote_normalized

    async def _execute_python(self, code: str) -> str:
        kernel_response = self.session.post(
            f"{self.settings.base_url}/api/kernels",
            json={"name": "python3"},
            timeout=30,
        )
        self._raise_for_response(kernel_response, "Start Jupyter kernel")
        kernel_id = kernel_response.json()["id"]
        session_id = str(uuid.uuid4())
        msg_id = str(uuid.uuid4())
        output = ""
        try:
            ws_url = (
                self.settings.base_url.replace("https://", "wss://").replace("http://", "ws://")
                + f"/api/kernels/{kernel_id}/channels?session_id={session_id}&token={quote(self.settings.token)}"
            )
            async with websockets.connect(
                ws_url,
                extra_headers={"Authorization": f"token {self.settings.token}"},
                open_timeout=30,
            ) as websocket:
                await websocket.send(
                    json.dumps(
                        {
                            "header": {
                                "msg_id": msg_id,
                                "username": "mv-generator",
                                "session": session_id,
                                "msg_type": "execute_request",
                                "version": "5.3",
                            },
                            "parent_header": {},
                            "metadata": {},
                            "channel": "shell",
                            "content": {
                                "code": code,
                                "silent": False,
                                "store_history": False,
                                "user_expressions": {},
                                "allow_stdin": False,
                                "stop_on_error": True,
                            },
                        }
                    )
                )
                while True:
                    raw = await asyncio.wait_for(websocket.recv(), timeout=self.settings.timeout_seconds)
                    message = json.loads(raw)
                    if message.get("parent_header", {}).get("msg_id") != msg_id:
                        continue
                    msg_type = message.get("header", {}).get("msg_type")
                    content = message.get("content", {})
                    if msg_type == "stream":
                        output += content.get("text", "")
                    elif msg_type == "error":
                        traceback = "\n".join(content.get("traceback", []))
                        raise RuntimeError(f"RunPod LatentSync failed: {content.get('ename')}: {content.get('evalue')}\n{traceback}")
                    elif msg_type == "execute_reply":
                        if content.get("status") != "ok":
                            raise RuntimeError(f"RunPod LatentSync failed: {content}")
                        return output
        finally:
            self.session.delete(f"{self.settings.base_url}/api/kernels/{kernel_id}", timeout=30)

    def _contents_url(self, remote_path: str) -> str:
        return f"{self.settings.base_url}/api/contents/{quote(self.contents_path(remote_path), safe='/')}"

    @staticmethod
    def _raise_for_response(response, label: str) -> None:
        if response.ok:
            return
        raise RuntimeError(f"{label} failed: HTTP {response.status_code} {response.text[:1000]}")


def _execution_code(latentsync_root: str, command: list[str]) -> str:
    return f"""
import os
import subprocess

os.chdir({json.dumps(latentsync_root)})
os.makedirs("input_segments", exist_ok=True)
os.makedirs("input_audio", exist_ok=True)
os.makedirs("output_segments", exist_ok=True)
cmd = {json.dumps(command)}
print("RUNNING:", " ".join(cmd), flush=True)
completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
print(completed.stdout, flush=True)
print("LATENTSYNC_RETURN_CODE=" + str(completed.returncode), flush=True)
if completed.returncode:
    raise SystemExit(completed.returncode)
"""


def _normalize_remote_path(remote_path: str) -> str:
    return remote_path.replace("\\", "/").lstrip("/")


def _contents_path_candidates(remote_path: str) -> list[str]:
    normalized = _normalize_remote_path(remote_path)
    candidates = [normalized]
    workspace_prefix = "workspace/"
    if normalized.startswith(workspace_prefix):
        candidates.append(normalized[len(workspace_prefix) :])
    return list(dict.fromkeys(candidates))


def _remote_parent(remote_path: str) -> str:
    return remote_path.replace("\\", "/").rstrip("/").rsplit("/", 1)[0]


def _relative_to_latentsync(remote_path: str, latentsync_root: str) -> str:
    root = latentsync_root.rstrip("/") + "/"
    if remote_path.startswith(root):
        return remote_path[len(root) :]
    return remote_path


def _safe_remote_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)

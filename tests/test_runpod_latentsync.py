import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.runpod_latentsync import (  # noqa: E402
    RunPodLatentSyncProvider,
    RunPodLatentSyncSettings,
    build_latentsync_command,
)


class RunPodLatentSyncTests(unittest.TestCase):
    def test_build_latentsync_command_uses_validated_stage2_recipe(self):
        command = build_latentsync_command(
            video_path="input_segments/job/range_001_source.mp4",
            audio_path="input_audio/job/range_001_audio.wav",
            output_path="output_segments/job/range_001_processed.mp4",
        )

        self.assertEqual(command[:3], ["python3", "-m", "scripts.inference"])
        self.assertIn("--unet_config_path", command)
        self.assertIn("configs/unet/stage2.yaml", command)
        self.assertIn("--inference_steps", command)
        self.assertIn("10", command)
        self.assertIn("--guidance_scale", command)
        self.assertIn("1.5", command)
        self.assertIn("--enable_deepcache", command)
        self.assertNotIn("stage2_512.yaml", command)

    @patch.dict(os.environ, {}, clear=True)
    def test_settings_from_env_requires_runpod_connection_details(self):
        with self.assertRaisesRegex(RuntimeError, "RUNPOD_JUPYTER_BASE_URL"):
            RunPodLatentSyncSettings.from_env()

    @patch.dict(
        os.environ,
        {
            "RUNPOD_JUPYTER_BASE_URL": "https://example-8888.proxy.runpod.net/",
            "RUNPOD_JUPYTER_TOKEN": "secret",
        },
        clear=True,
    )
    def test_settings_from_env_normalizes_base_url(self):
        settings = RunPodLatentSyncSettings.from_env()

        self.assertEqual(settings.base_url, "https://example-8888.proxy.runpod.net")
        self.assertEqual(settings.token, "secret")
        self.assertEqual(settings.latentsync_root, "/workspace/LatentSync")

    def test_check_connection_reports_unavailable_jupyter_api(self):
        provider = RunPodLatentSyncProvider(RunPodLatentSyncSettings("https://example.test", "secret"))
        provider.session = _FakeSession(get_responses={"https://example.test/api/kernelspecs": _FakeResponse(404)})

        with self.assertRaisesRegex(RuntimeError, "RunPod Jupyter API is not reachable"):
            provider.check_connection()

    def test_contents_path_supports_jupyter_root_at_workspace(self):
        provider = RunPodLatentSyncProvider(RunPodLatentSyncSettings("https://example.test", "secret"))
        provider.session = _FakeSession(
            get_responses={
                "https://example.test/api/contents/workspace/LatentSync": _FakeResponse(404),
                "https://example.test/api/contents/LatentSync": _FakeResponse(
                    200,
                    {"type": "directory"},
                ),
            }
        )

        path = provider.contents_path("/workspace/LatentSync/input_segments/job/range_001_source.mp4")

        self.assertEqual(path, "LatentSync/input_segments/job/range_001_source.mp4")


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, get_responses):
        self.get_responses = get_responses
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        return self.get_responses.get(url, _FakeResponse(404))


if __name__ == "__main__":
    unittest.main()

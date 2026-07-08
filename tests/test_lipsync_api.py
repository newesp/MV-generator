import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import main  # noqa: E402
from src.lipsync_existing_mv import MediaMetadata  # noqa: E402


class LipsyncExistingMvApiTests(unittest.TestCase):
    def setUp(self):
        main.job_store = main.JobStore()
        self.client = TestClient(main.app)

    @patch("main.process_lipsync_existing_mv_task")
    def test_create_lipsync_existing_mv_job_starts_automatic_runpod_job(self, process_mock):
        response = self.client.post(
            "/lipsync-existing-mv",
            data={"ranges": '[{"start": 6, "end": 13}]'},
            files={"file": ("source.mp4", io.BytesIO(b"video"), "video/mp4")},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"], "lipsync_existing_mv")
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["stage"], "queued_auto")
        self.assertIn("RunPod", payload["message"])
        process_mock.assert_called_once()

    @patch("main.verify_final_video")
    @patch("main.stitch_processed_segments")
    def test_resume_stitching_completes_job_when_all_processed_segments_exist(self, stitch_mock, verify_mock):
        verify_mock.return_value = MediaMetadata(duration=28.672, width=1280, height=720, fps="24/1")
        job = main.job_store.create_job("lipsync_existing_mv")
        job_dir = Path(main.OUTPUTS_DIR) / job["job_id"]
        processed_dir = job_dir / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        (processed_dir / "range_001_processed.mp4").write_bytes(b"processed")
        source = job_dir / "source.mp4"
        source.write_bytes(b"source")
        main.job_store.update_job(
            job["job_id"],
            status="waiting_manual",
            stage="runpod_manual",
            metadata={"duration": 28.672},
            ranges=[{"start": 6.0, "end": 13.0, "duration": 7.0}],
            artifacts={"job_dir": str(job_dir), "source": str(source)},
        )

        response = self.client.post(f"/jobs/{job['job_id']}/resume-stitch")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["stage"], "verified")
        self.assertIn("final", payload["artifacts"])
        stitch_mock.assert_called_once()

    @patch("main.verify_final_video")
    @patch("main.stitch_processed_segments")
    @patch("main.RunPodLatentSyncProvider")
    @patch("main.prepare_lipsync_existing_mv_job")
    def test_process_lipsync_existing_mv_task_runs_runpod_then_stitches(
        self,
        prepare_mock,
        provider_class_mock,
        stitch_mock,
        verify_mock,
    ):
        prepared = _prepared_job_stub()
        prepare_mock.return_value = prepared
        provider = provider_class_mock.from_env.return_value
        processed = Path(prepared.artifacts()["job_dir"]) / "processed" / "range_001_processed.mp4"
        provider.process_prepared_job.return_value = [processed]
        verify_mock.return_value = MediaMetadata(duration=28.672, width=1280, height=720, fps="24/1")
        job = main.job_store.create_job("lipsync_existing_mv")

        main.process_lipsync_existing_mv_task(
            job_id=job["job_id"],
            source_path=Path("source.mp4"),
            ranges_json='[{"start": 6, "end": 13}]',
        )

        provider.process_prepared_job.assert_called_once()
        stitch_mock.assert_called_once()
        completed = main.job_store.get_job(job["job_id"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["stage"], "verified")


class _PreparedJobStub:
    job_id = "job-123"
    job_dir = Path("outputs/job-123")
    source_video = Path("outputs/job-123/source.mp4")
    metadata = MediaMetadata(duration=28.672, width=1280, height=720, fps="24/1")
    ranges = []

    def __init__(self):
        from src.lipsync_existing_mv import LipsyncRange

        self.ranges = [LipsyncRange(6.0, 13.0)]

    def artifacts(self):
        return {
            "job_dir": "outputs/job-123",
            "source": "outputs/job-123/source.mp4",
            "runpod_bundle": "outputs/job-123/runpod_manual_bundle",
            "segments": ["outputs/job-123/segments/range_001_source.mp4"],
            "segment_audio": ["outputs/job-123/audio/range_001_audio.wav"],
        }


def _prepared_job_stub():
    return _PreparedJobStub()


if __name__ == "__main__":
    unittest.main()

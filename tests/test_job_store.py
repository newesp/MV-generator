import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.job_store import JobStore  # noqa: E402


class JobStoreTests(unittest.TestCase):
    def test_create_job_returns_serializable_lipsync_job(self):
        store = JobStore()

        job = store.create_job("lipsync_existing_mv")

        self.assertEqual(job["workflow"], "lipsync_existing_mv")
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["stage"], "queued")
        self.assertEqual(job["progress"], 0.0)
        self.assertIn("job_id", job)
        self.assertIn("created_at", job)

    def test_update_job_merges_artifacts_and_extra_fields(self):
        store = JobStore()
        job = store.create_job("lipsync_existing_mv")

        updated = store.update_job(
            job["job_id"],
            status="waiting_manual",
            stage="runpod_manual",
            progress=0.62,
            message="Upload prepared segments to RunPod.",
            artifacts={"final": "outputs/job/final.mp4"},
            ranges=[{"start": 6, "end": 13}],
        )

        self.assertEqual(updated["status"], "waiting_manual")
        self.assertEqual(updated["artifacts"]["final"], "outputs/job/final.mp4")
        self.assertEqual(updated["ranges"], [{"start": 6, "end": 13}])

    def test_get_job_returns_copy(self):
        store = JobStore()
        job = store.create_job("lipsync_existing_mv")

        fetched = store.get_job(job["job_id"])
        fetched["status"] = "mutated"

        self.assertEqual(store.get_job(job["job_id"])["status"], "pending")


if __name__ == "__main__":
    unittest.main()

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.lipsync_existing_mv import (  # noqa: E402
    MediaMetadata,
    RangeValidationError,
    create_manual_runpod_bundle,
    parse_lipsync_ranges,
    prepare_lipsync_existing_mv_job,
    stitch_processed_segments,
)


class LipsyncExistingMvRangeTests(unittest.TestCase):
    def test_parse_lipsync_ranges_accepts_multiple_sorted_ranges(self):
        ranges = parse_lipsync_ranges(
            '[{"start": 6, "end": 13}, {"start": 16.25, "end": 23}]',
            duration=28.672,
        )

        self.assertEqual([(item.start, item.end) for item in ranges], [(6.0, 13.0), (16.25, 23.0)])

    def test_parse_lipsync_ranges_rejects_overlapping_ranges(self):
        with self.assertRaisesRegex(RangeValidationError, "overlap"):
            parse_lipsync_ranges(
                [{"start": 6, "end": 13}, {"start": 12.9, "end": 23}],
                duration=28.672,
            )

    def test_parse_lipsync_ranges_rejects_ranges_outside_duration(self):
        with self.assertRaisesRegex(RangeValidationError, "duration"):
            parse_lipsync_ranges([{"start": 6, "end": 30}], duration=28.672)


class LipsyncExistingMvPipelineTests(unittest.TestCase):
    def test_create_manual_runpod_bundle_writes_manifest_and_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp)
            segment_a = job_dir / "segments" / "range_001_source.mp4"
            segment_b = job_dir / "segments" / "range_002_source.mp4"
            audio_a = job_dir / "audio" / "range_001_audio.m4a"
            audio_b = job_dir / "audio" / "range_002_audio.m4a"
            segment_a.parent.mkdir()
            audio_a.parent.mkdir()
            segment_a.write_bytes(b"segment-a")
            segment_b.write_bytes(b"segment-b")
            audio_a.write_bytes(b"audio-a")
            audio_b.write_bytes(b"audio-b")

            bundle = create_manual_runpod_bundle(
                job_id="job-123",
                job_dir=job_dir,
                source_video=job_dir / "source.mp4",
                ranges=parse_lipsync_ranges([{"start": 6, "end": 13}, {"start": 16, "end": 23}], 28.672),
                segment_video_paths=[segment_a, segment_b],
                segment_audio_paths=[audio_a, audio_b],
            )

            manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            instructions = (bundle / "README.md").read_text(encoding="utf-8")

            self.assertEqual(manifest["job_id"], "job-123")
            self.assertEqual(len(manifest["segments"]), 2)
            self.assertEqual(manifest["segments"][0]["target_output"], "range_001_processed.mp4")
            self.assertEqual(manifest["segments"][0]["audio_upload_name"], "range_001_audio.m4a")
            self.assertIn("/workspace/LatentSync", instructions)
            self.assertIn("range_002_source.mp4", instructions)
            self.assertIn("range_002_audio.m4a", instructions)
            self.assertIn("--unet_config_path configs/unet/stage2.yaml", instructions)
            self.assertIn("--inference_steps 10", instructions)
            self.assertNotIn("stage2_512.yaml", instructions)

    @patch("src.lipsync_existing_mv.probe_media_metadata")
    @patch("src.lipsync_existing_mv.run_ffmpeg")
    def test_prepare_lipsync_existing_mv_job_extracts_each_target_segment(self, run_ffmpeg_mock, metadata_mock):
        metadata_mock.return_value = MediaMetadata(duration=28.672, width=1280, height=720, fps="24/1")

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.write_bytes(b"mv")

            result = prepare_lipsync_existing_mv_job(
                job_id="job-123",
                source_video=source,
                ranges_json='[{"start": 6, "end": 13}, {"start": 16, "end": 23}]',
                outputs_dir=Path(tmp) / "outputs",
            )

            labels = [call.args[1] for call in run_ffmpeg_mock.call_args_list]

            self.assertEqual(result.metadata.duration, 28.672)
            self.assertEqual(len(result.segment_video_paths), 2)
            self.assertEqual(
                labels,
                [
                    "Extract target segment 1",
                    "Extract target audio 1",
                    "Extract target segment 2",
                    "Extract target audio 2",
                ],
            )
            self.assertTrue(result.runpod_bundle_dir.name == "runpod_manual_bundle")
            self.assertEqual(result.segment_audio_paths[0].suffix, ".wav")
            audio_cmd = run_ffmpeg_mock.call_args_list[1].args[0]
            self.assertIn("-ar", audio_cmd)
            self.assertIn("16000", audio_cmd)
            self.assertIn("-ac", audio_cmd)
            self.assertIn("1", audio_cmd)
            self.assertIn("pcm_s16le", audio_cmd)

    @patch("src.lipsync_existing_mv.probe_media_metadata")
    @patch("src.lipsync_existing_mv.run_ffmpeg")
    def test_stitch_processed_segments_keeps_original_gaps_and_inserts_processed_ranges(
        self, run_ffmpeg_mock, metadata_mock
    ):
        metadata_mock.return_value = MediaMetadata(duration=28.672, width=1280, height=720, fps="24/1")
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp)
            source = job_dir / "source.mp4"
            processed_a = job_dir / "range_001_processed.mp4"
            processed_b = job_dir / "range_002_processed.mp4"
            final = job_dir / "final.mp4"
            for path in [source, processed_a, processed_b]:
                path.write_bytes(b"video")

            stitch_processed_segments(
                source_video=source,
                ranges=parse_lipsync_ranges([{"start": 6, "end": 13}, {"start": 16, "end": 23}], 28.672),
                processed_segment_paths=[processed_a, processed_b],
                output_path=final,
                duration=28.672,
            )

            labels = [call.args[1] for call in run_ffmpeg_mock.call_args_list]
            self.assertEqual(
                labels,
                [
                    "Extract original gap 1",
                    "Normalize processed segment 1",
                    "Extract original gap 2",
                    "Normalize processed segment 2",
                    "Extract original gap 3",
                    "Stitch lip-sync existing MV",
                ],
            )
            concat_file = final.parent / "stitch_parts.txt"
            concat_text = concat_file.read_text(encoding="utf-8")
            self.assertIn(str((final.parent / "original_gap_001.mp4").resolve()).replace("\\", "/"), concat_text)
            self.assertIn(str((final.parent / "processed_video_001.mp4").resolve()).replace("\\", "/"), concat_text)
            self.assertIn(str((final.parent / "processed_video_002.mp4").resolve()).replace("\\", "/"), concat_text)
            stitch_cmd = run_ffmpeg_mock.call_args_list[-1].args[0]
            self.assertIn(str(source), stitch_cmd)
            self.assertIn("1:a:0?", stitch_cmd)
            self.assertIn("-c:a", stitch_cmd)
            self.assertIn("copy", stitch_cmd)
            normalize_cmd = run_ffmpeg_mock.call_args_list[1].args[0]
            self.assertIn("-t", normalize_cmd)
            self.assertIn("7.000", normalize_cmd)


if __name__ == "__main__":
    unittest.main()

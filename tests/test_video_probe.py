import json
import pathlib
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock


SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_DIR / "tests"))
from bytecode_guard import install as install_bytecode_guard  # noqa: E402

install_bytecode_guard(SKILL_DIR)
sys.path.insert(0, str(SKILL_DIR / "scripts"))


from video_probe import classify_video, exit_code_for_severity, main, parse_ffprobe_json, sample_frame_stats  # noqa: E402


class VideoProbeTests(unittest.TestCase):
    def test_parse_ffprobe_json_extracts_core_metadata(self):
        payload = {
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30000/1001",
                    "nb_frames": "300",
                    "bit_rate": "8000000",
                    "codec_name": "h264",
                }
            ],
            "format": {"duration": "10.01", "size": "10000000"},
        }

        metadata = parse_ffprobe_json(payload)

        self.assertEqual(metadata["width"], 1920)
        self.assertEqual(metadata["height"], 1080)
        self.assertAlmostEqual(metadata["fps"], 29.970, places=3)
        self.assertEqual(metadata["frame_count"], 300)
        self.assertEqual(metadata["video_bitrate"], 8000000)
        self.assertEqual(metadata["duration"], 10.01)
        self.assertEqual(metadata["codec"], "h264")

    def test_classify_video_flags_black_frames_when_all_samples_are_dark(self):
        metadata = {"duration": 10.0, "width": 1920, "height": 1080, "fps": 30.0}
        frame_stats = [
            {"timestamp": 0.0, "mean": 0.0, "stdev": 0.0},
            {"timestamp": 2.5, "mean": 0.0, "stdev": 0.0},
            {"timestamp": 5.0, "mean": 1.0, "stdev": 0.5},
            {"timestamp": 7.5, "mean": 0.0, "stdev": 0.0},
            {"timestamp": 9.9, "mean": 0.0, "stdev": 0.0},
        ]

        result = classify_video(metadata, frame_stats)

        self.assertTrue(result["risks"]["black_frame_risk"])
        self.assertEqual(result["black_frame_ratio"], 1.0)
        self.assertIn("P0", result["severity"])

    def test_classify_video_accepts_varied_visible_frames(self):
        metadata = {"duration": 10.0, "width": 1920, "height": 1080, "fps": 30.0}
        frame_stats = [
            {"timestamp": 0.0, "mean": 24.0, "stdev": 20.0},
            {"timestamp": 2.5, "mean": 82.0, "stdev": 44.0},
            {"timestamp": 5.0, "mean": 133.0, "stdev": 51.0},
            {"timestamp": 7.5, "mean": 170.0, "stdev": 39.0},
            {"timestamp": 9.9, "mean": 210.0, "stdev": 34.0},
        ]

        result = classify_video(metadata, frame_stats)

        self.assertFalse(result["risks"]["black_frame_risk"])
        self.assertFalse(result["risks"]["static_frame_risk"])
        self.assertEqual(result["severity"], "pass")

    def test_classify_video_does_not_treat_white_slide_with_text_as_blank(self):
        metadata = {"duration": 10.0, "width": 1920, "height": 1080, "fps": 30.0}
        frame_stats = [
            {"timestamp": 0.0, "mean": 252.0, "stdev": 18.0},
            {"timestamp": 2.5, "mean": 252.0, "stdev": 18.0},
            {"timestamp": 5.0, "mean": 252.0, "stdev": 18.0},
            {"timestamp": 7.5, "mean": 252.0, "stdev": 18.0},
            {"timestamp": 9.9, "mean": 252.0, "stdev": 18.0},
        ]

        result = classify_video(metadata, frame_stats)

        self.assertFalse(result["risks"]["white_frame_risk"])
        self.assertEqual(result["severity"], "P1")

    def test_classify_video_flags_uniform_white_frames(self):
        metadata = {"duration": 10.0, "width": 1920, "height": 1080, "fps": 30.0}
        frame_stats = [
            {"timestamp": 0.0, "mean": 255.0, "stdev": 0.0},
            {"timestamp": 2.5, "mean": 255.0, "stdev": 0.0},
            {"timestamp": 5.0, "mean": 255.0, "stdev": 0.0},
            {"timestamp": 7.5, "mean": 255.0, "stdev": 0.0},
            {"timestamp": 9.9, "mean": 255.0, "stdev": 0.0},
        ]

        result = classify_video(metadata, frame_stats)

        self.assertTrue(result["risks"]["white_frame_risk"])
        self.assertEqual(result["severity"], "P0")

    def test_exit_code_for_severity_blocks_p0_and_p1(self):
        self.assertEqual(exit_code_for_severity("P0"), 2)
        self.assertEqual(exit_code_for_severity("P1"), 1)
        self.assertEqual(exit_code_for_severity("pass"), 0)

    def test_sample_frame_stats_rejects_incomplete_raw_frame(self):
        completed = subprocess.CompletedProcess(["ffmpeg"], 0, stdout=b"\x00" * 3)
        metadata = {"duration": 1.0, "width": 2, "height": 2, "fps": 1.0}

        with mock.patch("video_probe.subprocess.run", return_value=completed):
            with self.assertRaises(RuntimeError):
                sample_frame_stats("render.mp4", metadata, count=1)

    def test_main_reports_invalid_ffprobe_json_without_traceback(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            video = pathlib.Path(tmp) / "render.mp4"
            video.write_bytes(b"not a real video")
            completed = subprocess.CompletedProcess(["ffprobe"], 0, stdout="{bad json")

            stdout = StringIO()
            stderr = StringIO()
            with mock.patch("video_probe.subprocess.run", return_value=completed):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = main([str(video), "--json"])

            self.assertEqual(code, 2)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["severity"], "P0")
            self.assertEqual(payload["error"], "ffprobe_failed")
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_main_reports_ffmpeg_sampling_failure_with_metadata(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            video = pathlib.Path(tmp) / "render.mp4"
            video.write_bytes(b"not a real video")
            payload = {
                "streams": [{"codec_type": "video", "width": 2, "height": 2, "avg_frame_rate": "1/1"}],
                "format": {"duration": "1.0"},
            }
            stdout = StringIO()
            stderr = StringIO()
            with mock.patch("video_probe.run_ffprobe", return_value=payload):
                with mock.patch("video_probe.sample_frame_stats", side_effect=FileNotFoundError("ffmpeg")):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        code = main([str(video), "--json"])

            self.assertEqual(code, 3)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["severity"], "P1")
            self.assertEqual(result["error"], "frame_sampling_failed")
            self.assertEqual(result["metadata"]["width"], 2)
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_main_returns_nonzero_for_detected_p0_visual_risk(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            video = pathlib.Path(tmp) / "render.mp4"
            video.write_bytes(b"not a real video")
            payload = {
                "streams": [{"codec_type": "video", "width": 2, "height": 2, "avg_frame_rate": "1/1"}],
                "format": {"duration": "1.0"},
            }
            frame_stats = [
                {"timestamp": 0.0, "mean": 0.0, "stdev": 0.0},
                {"timestamp": 0.2, "mean": 0.0, "stdev": 0.0},
                {"timestamp": 0.4, "mean": 0.0, "stdev": 0.0},
            ]
            stdout = StringIO()
            with mock.patch("video_probe.run_ffprobe", return_value=payload):
                with mock.patch("video_probe.sample_frame_stats", return_value=frame_stats):
                    with redirect_stdout(stdout):
                        code = main([str(video), "--json"])

            self.assertEqual(code, 2)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["severity"], "P0")

    def test_main_returns_nonzero_for_detected_p1_static_risk(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            video = pathlib.Path(tmp) / "render.mp4"
            video.write_bytes(b"not a real video")
            payload = {
                "streams": [{"codec_type": "video", "width": 2, "height": 2, "avg_frame_rate": "1/1"}],
                "format": {"duration": "1.0"},
            }
            frame_stats = [
                {"timestamp": 0.0, "mean": 120.0, "stdev": 10.0},
                {"timestamp": 0.2, "mean": 120.5, "stdev": 10.2},
                {"timestamp": 0.4, "mean": 121.0, "stdev": 10.3},
            ]
            stdout = StringIO()
            with mock.patch("video_probe.run_ffprobe", return_value=payload):
                with mock.patch("video_probe.sample_frame_stats", return_value=frame_stats):
                    with redirect_stdout(stdout):
                        code = main([str(video), "--json"])

            self.assertEqual(code, 1)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["severity"], "P1")


if __name__ == "__main__":
    unittest.main()

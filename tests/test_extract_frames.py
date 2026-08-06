import pathlib
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock


SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_DIR / "tests"))
from bytecode_guard import install as install_bytecode_guard  # noqa: E402

install_bytecode_guard(SKILL_DIR)
sys.path.insert(0, str(SKILL_DIR / "scripts"))


from extract_frames import build_extract_commands, clear_managed_outputs, main, run_commands, sample_timestamps  # noqa: E402


class ExtractFramesTests(unittest.TestCase):
    def test_sample_timestamps_covers_video_and_clamps_last_frame(self):
        self.assertEqual(sample_timestamps(10.0, count=5), [0.0, 2.38, 4.75, 7.12, 9.5])

    def test_sample_timestamps_handles_short_video(self):
        self.assertEqual(sample_timestamps(1.0, count=5), [0.0, 0.2, 0.4, 0.6, 0.8])

    def test_build_extract_commands_creates_one_command_per_frame_plus_contact_sheet(self):
        commands = build_extract_commands(
            ffmpeg="ffmpeg",
            video="input.mp4",
            out_dir="frames",
            timestamps=[0.0, 2.5],
        )

        self.assertEqual(len(commands["frames"]), 2)
        self.assertIn("frame-001-0.00s.png", commands["frames"][0][-1])
        self.assertIn("frame-002-2.50s.png", commands["frames"][1][-1])
        self.assertTrue(commands["contact_sheet"][-1].endswith("contact-sheet.png"))
        self.assertIn("frames", commands["contact_sheet"][-1])
        self.assertNotIn("glob", commands["contact_sheet"])
        self.assertIn("xstack=inputs=2", " ".join(commands["contact_sheet"]))
        self.assertEqual(commands["contact_sheet"].count("-i"), 2)

    def test_clear_managed_outputs_removes_only_video_qa_artifacts(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = pathlib.Path(tmp)
            (out_dir / "frame-001-0.00s.png").write_bytes(b"old frame")
            (out_dir / "frame-999-stale.png").write_bytes(b"stale frame")
            (out_dir / "contact-sheet.png").write_bytes(b"old sheet")
            (out_dir / "notes.txt").write_text("keep", encoding="utf-8")

            clear_managed_outputs(out_dir)

            self.assertFalse((out_dir / "frame-001-0.00s.png").exists())
            self.assertFalse((out_dir / "frame-999-stale.png").exists())
            self.assertFalse((out_dir / "contact-sheet.png").exists())
            self.assertTrue((out_dir / "notes.txt").exists())

    def test_run_commands_rejects_missing_frame_output(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            frame_path = pathlib.Path(tmp) / "frame-001-0.00s.png"
            commands = {
                "frames": [["ffmpeg", "-i", "input.mp4", str(frame_path)]],
                "contact_sheet": ["ffmpeg", "-i", str(frame_path), str(pathlib.Path(tmp) / "contact-sheet.png")],
            }

            with mock.patch("extract_frames.subprocess.run"):
                with self.assertRaises(RuntimeError):
                    run_commands(commands)

    def test_main_reports_ffprobe_failure_without_traceback(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            video = pathlib.Path(tmp) / "render.mp4"
            video.write_bytes(b"not a real video")
            error = subprocess.CalledProcessError(1, ["ffprobe"], stderr="bad file")

            stderr = StringIO()
            with mock.patch("extract_frames.run_ffprobe_duration", side_effect=error):
                with redirect_stderr(stderr):
                    code = main([str(video), "--out", str(pathlib.Path(tmp) / "qa-frames")])

            self.assertEqual(code, 2)
            self.assertIn("P0:", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_main_reports_ffmpeg_failure_without_traceback(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            video = pathlib.Path(tmp) / "render.mp4"
            video.write_bytes(b"not a real video")
            error = subprocess.CalledProcessError(1, ["ffmpeg"], stderr="decode failed")

            stderr = StringIO()
            with mock.patch("extract_frames.run_ffprobe_duration", return_value=1.0):
                with mock.patch("extract_frames.run_commands", side_effect=error):
                    with redirect_stderr(stderr):
                        code = main([str(video), "--out", str(pathlib.Path(tmp) / "qa-frames")])

            self.assertEqual(code, 3)
            self.assertIn("P1:", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

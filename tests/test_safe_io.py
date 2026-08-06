import pathlib
import sys
import tempfile
import unittest


SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_DIR / "tests"))
from bytecode_guard import install as install_bytecode_guard  # noqa: E402

install_bytecode_guard(SKILL_DIR)
sys.path.insert(0, str(SKILL_DIR / "scripts"))


from safe_io import UnsafePathError, assert_safe_output_dir, assert_safe_output_path  # noqa: E402


class SafeIOTests(unittest.TestCase):
    def test_output_file_refuses_existing_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = pathlib.Path(tmp) / "video-qa-report.md"
            report.write_text("old report", encoding="utf-8")

            with self.assertRaises(UnsafePathError):
                assert_safe_output_path(report, allowed_suffixes={".md"})

            self.assertEqual(assert_safe_output_path(report, overwrite=True, allowed_suffixes={".md"}), report.resolve())

    def test_output_dir_refuses_nonempty_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = pathlib.Path(tmp) / "qa-frames"
            out_dir.mkdir()
            (out_dir / "contact-sheet.png").write_bytes(b"old")

            with self.assertRaises(UnsafePathError):
                assert_safe_output_dir(out_dir)

            self.assertEqual(assert_safe_output_dir(out_dir, overwrite=True), out_dir.resolve())

    def test_output_path_refuses_skill_directories(self):
        with self.assertRaises(UnsafePathError):
            assert_safe_output_path(SKILL_DIR / "video-qa-report.md", allowed_suffixes={".md"})

        with self.assertRaises(UnsafePathError):
            assert_safe_output_dir(SKILL_DIR / "qa-frames")

    def test_output_path_refuses_plugin_directories(self):
        plugin_root = pathlib.Path.home() / ".codex" / "plugins" / ".remote-plugin-install-staging"
        plugin_cache = pathlib.Path.home() / ".codex" / "plugins" / "cache" / "bundle"
        agent_plugin = pathlib.Path.home() / ".agents" / "plugins" / "cache"

        with self.assertRaises(UnsafePathError):
            assert_safe_output_path(plugin_root / "video-qa-report.md", allowed_suffixes={".md"})
        with self.assertRaises(UnsafePathError):
            assert_safe_output_dir(plugin_cache / "qa-frames")
        with self.assertRaises(UnsafePathError):
            assert_safe_output_dir(agent_plugin / "qa-frames")

    def test_output_path_refuses_broad_home_roots(self):
        with self.assertRaises(UnsafePathError):
            assert_safe_output_path(pathlib.Path.home() / "video-qa-report.md", allowed_suffixes={".md"})

        with self.assertRaises(UnsafePathError):
            assert_safe_output_dir(pathlib.Path.home())

    def test_output_path_refuses_source_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "render.mp4"
            source.write_bytes(b"video")

            with self.assertRaises(UnsafePathError):
                assert_safe_output_path(source, source_paths=[source])


if __name__ == "__main__":
    unittest.main()

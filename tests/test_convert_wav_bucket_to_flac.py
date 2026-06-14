import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "convert-wav-bucket-to-flac.py"
SPEC = importlib.util.spec_from_file_location("convert_wav_bucket_to_flac", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ConvertWavBucketToFlacTest(unittest.TestCase):
    def test_derive_dest_bucket_from_wav_suffix(self):
        self.assertEqual(module.derive_dest_bucket("metal-wav", None), "metal")

    def test_derive_dest_bucket_requires_explicit_dest_without_suffix(self):
        with self.assertRaises(module.ConvertBucketError):
            module.derive_dest_bucket("metal", None)

    def test_album_dir_strips_disc_folder(self):
        rel = Path("Various Artists") / "NOW - Yearbook 1990 (2024)" / "CD01" / "01 Track.wav"
        album_dir = module.album_dir_from_relative_path(rel)
        self.assertEqual(album_dir, Path("Various Artists") / "NOW - Yearbook 1990 (2024)")

    def test_plan_actions_converts_wav_and_copies_sidecars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            music_root = Path(tmpdir)
            source_root = music_root / "metal-wav"
            dest_root = music_root / "metal"
            album_dir = source_root / "Death" / "Human (1991)"
            album_dir.mkdir(parents=True)
            (album_dir / "01 Death - Flattening Of Emotions.wav").write_bytes(b"fake")
            (album_dir / "Folder.jpg").write_bytes(b"art")
            (album_dir / "notes.txt").write_text("hello", encoding="utf-8")

            planned = module.plan_actions(source_root, dest_root, copy_flac=False)

        self.assertEqual(len(planned), 3)
        convert = [item for item in planned if item.kind == "convert"][0]
        self.assertEqual(
            convert.dest,
            dest_root / "Death" / "Human (1991)" / "01 Death - Flattening Of Emotions.flac",
        )
        copies = [item for item in planned if item.kind == "copy"]
        self.assertEqual({item.dest.name for item in copies}, {"Folder.jpg", "notes.txt"})

    def test_plan_actions_copies_flac_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            music_root = Path(tmpdir)
            source_root = music_root / "misc-wav"
            dest_root = music_root / "misc"
            album_dir = source_root / "Abba" / "Gold"
            album_dir.mkdir(parents=True)
            (album_dir / "01 Abba - Dancing Queen.flac").write_bytes(b"fake")

            planned = module.plan_actions(source_root, dest_root, copy_flac=True)

        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0].kind, "copy")
        self.assertEqual(planned[0].dest, dest_root / "Abba" / "Gold" / "01 Abba - Dancing Queen.flac")

    def test_plan_actions_resume_skips_existing_destination_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            music_root = Path(tmpdir)
            source_root = music_root / "metal-wav"
            dest_root = music_root / "metal"
            album_dir = source_root / "Death" / "Human (1991)"
            dest_album_dir = dest_root / "Death" / "Human (1991)"
            album_dir.mkdir(parents=True)
            dest_album_dir.mkdir(parents=True)
            (album_dir / "01 Death - Flattening Of Emotions.wav").write_bytes(b"fake")
            (album_dir / "Folder.jpg").write_bytes(b"art")
            (dest_album_dir / "01 Death - Flattening Of Emotions.flac").write_bytes(b"done")
            (dest_album_dir / "Folder.jpg").write_bytes(b"done")

            planned = module.plan_actions(source_root, dest_root, copy_flac=True, resume=True)

        self.assertEqual(planned, [])

    def test_execute_actions_logs_and_skips_failed_conversion(self):
        logger = module.Logger()
        planned = [
            module.PlannedAction(
                source=Path("/tmp/bad.wav"),
                dest=Path("/tmp/bad.flac"),
                kind="convert",
                album_dir=None,
            ),
            module.PlannedAction(
                source=Path("/tmp/good.jpg"),
                dest=Path("/tmp/good.jpg"),
                kind="copy",
                album_dir=None,
            ),
        ]

        with (
            mock.patch.object(
                module,
                "convert_wav_to_flac",
                side_effect=subprocess.CalledProcessError(183, ["ffmpeg"]),
            ),
            mock.patch.object(module, "copy_file") as copy_mock,
        ):
            completed, skipped = module.execute_actions(planned, logger)

        copy_mock.assert_called_once()
        self.assertEqual(completed, 1)
        self.assertEqual(skipped, 1)


if __name__ == "__main__":
    unittest.main()

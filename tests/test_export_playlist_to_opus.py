import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export-playlist-to-opus.py"
SPEC = importlib.util.spec_from_file_location("export_playlist_to_opus", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ExportPlaylistToOpusTest(unittest.TestCase):
    def test_destination_filename_strips_track_number_and_sets_opus_suffix(self):
        result = module.destination_filename(Path("01 Artist - Song.flac"))

        self.assertEqual(result, "Artist - Song.opus")

    def test_decode_playlist_path_maps_unc_share_to_mount_root(self):
        playlist = Path("/tmp/exyu.m3u")
        result = module.decode_playlist_path(
            r"\\192.168.100.83\xnas\music\exyu\Artist\Album\01 Artist - Song.flac",
            playlist,
            Path("/mnt/nas"),
        )

        self.assertEqual(result, Path("/mnt/nas/music/exyu/Artist/Album/01 Artist - Song.flac"))

    def test_build_export_actions_adds_suffix_for_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first = tmp_path / "a" / "01 Artist - Song.flac"
            second = tmp_path / "b" / "02 Artist - Song.flac"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_bytes(b"one")
            second.write_bytes(b"two")

            actions = module.build_export_actions([first, second], tmp_path / "out")

            self.assertEqual(actions[0].dest.name, "Artist - Song.opus")
            self.assertEqual(actions[1].dest.name, "Artist - Song-2.opus")
            self.assertFalse(actions[0].renamed)
            self.assertTrue(actions[1].renamed)

    def test_analyze_replaygain_parses_ebur128_output(self):
        stderr = """
  Integrated loudness:
    I:         -10.2 LUFS
    Threshold: -20.0 LUFS

  True peak:
    Peak:       -1.5 dBFS
"""
        loudness = module.LOUDNESS_RE.findall(stderr)
        peak = module.PEAK_RE.findall(stderr)

        self.assertEqual(loudness[-1], "-10.2")
        self.assertEqual(peak[-1], "-1.5")

    def test_source_folder_art_finds_folder_jpg(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            art = album / "Folder.jpg"
            track = album / "01 Artist - Song.flac"
            art.write_bytes(b"jpg")
            track.write_bytes(b"flac")

            self.assertEqual(module.source_folder_art(track), art)

    def test_build_ffmetadata_lines_include_replaygain_and_picture(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp) / "Folder.jpg"
            art.write_bytes(b"jpg")

            lines = module.build_ffmetadata_lines(
                module.ReplayGainResult(gain_db=-3.25, peak_linear=0.891234),
                art,
            )

            self.assertEqual(lines[0], ";FFMETADATA1")
            self.assertIn("REPLAYGAIN_TRACK_GAIN=-3.25 dB", lines)
            self.assertIn("REPLAYGAIN_TRACK_PEAK=0.891234", lines)
            self.assertIn("REPLAYGAIN_REFERENCE_LOUDNESS=89.0 dB", lines)
            self.assertTrue(lines[-1].startswith("METADATA_BLOCK_PICTURE="))

    def test_run_captured_replaces_invalid_utf8(self):
        result = module.run_captured(
            [
                "python3",
                "-c",
                "import sys; sys.stderr.buffer.write(b'Queensr\\xffche\\n')",
            ]
        )

        self.assertEqual(result.stderr, "Queensr\ufffdche\n")

    def test_cleanup_stale_temp_files_removes_only_exporter_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            stale_audio = dest / "playlist-opus-audio-abc.opus"
            stale_final = dest / "playlist-opus-final-abc.opus"
            stale_meta = dest / "playlist-opus-meta-abc.ffmeta"
            real_export = dest / "Artist - Song.opus"

            for path in (stale_audio, stale_final, stale_meta, real_export):
                path.write_bytes(b"x")

            removed = module.cleanup_stale_temp_files(dest)

            self.assertEqual(removed, sorted([stale_audio, stale_final, stale_meta]))
            self.assertFalse(stale_audio.exists())
            self.assertFalse(stale_final.exists())
            self.assertFalse(stale_meta.exists())
            self.assertTrue(real_export.exists())


if __name__ == "__main__":
    unittest.main()

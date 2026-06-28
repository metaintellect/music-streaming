import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export-playlist-library.py"
SPEC = importlib.util.spec_from_file_location("export_playlist_library", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ExportPlaylistLibraryTest(unittest.TestCase):
    def test_destination_filename_strips_track_number_and_uses_selected_format(self):
        self.assertEqual(
            module.destination_filename(Path("01 Artist - Song.flac"), "opus"),
            "Artist - Song.opus",
        )
        self.assertEqual(
            module.destination_filename(Path("01 Artist - Song.flac"), "flac"),
            "Artist - Song.flac",
        )
        self.assertEqual(
            module.destination_filename(
                Path("01 Artist - Song.flac"),
                "flac",
                track_number=1,
                total_tracks=12,
            ),
            "01 Artist - Song.flac",
        )

    def test_parse_track_artist_title_uses_filename(self):
        artist, title = module.parse_track_artist_title(Path("01 Artist - Song Title.flac"))

        self.assertEqual(artist, "Artist")
        self.assertEqual(title, "Song Title")

    def test_encoder_args_switches_between_opus_and_flac(self):
        self.assertEqual(
            module.encoder_args("opus", 128, "vbr"),
            ["-c:a", "libopus", "-b:a", "128k", "-application", "audio", "-vbr", "on"],
        )
        self.assertEqual(
            module.encoder_args("flac", 128, "vbr"),
            ["-c:a", "flac", "-compression_level", "5"],
        )

    def test_playlist_metadata_pairs_build_compilation_tags(self):
        self.assertEqual(
            module.playlist_metadata_pairs(
                "exyu",
                "Tony Cetinski",
                "Dom",
                "Various Artists",
                "playlist",
            ),
            [
                ("TITLE", "Dom"),
                ("ARTIST", "Tony Cetinski"),
                ("ALBUM", "exyu"),
                ("ALBUMARTIST", "Various Artists"),
                ("GENRE", "playlist"),
                ("COMPILATION", "1"),
            ],
        )
        self.assertEqual(
            module.playlist_metadata_pairs(
                "exyu",
                "Tony Cetinski",
                "Dom",
                "Various Artists",
                "playlist",
                track_number=4,
                track_total=22,
            )[-2:],
            [("TRACKNUMBER", "4"), ("TRACKTOTAL", "22")],
        )

    def test_build_export_actions_uses_playlist_order_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first = tmp_path / "01 Artist - Alpha.flac"
            second = tmp_path / "02 Artist - Beta.flac"
            first.write_bytes(b"a")
            second.write_bytes(b"b")

            actions = module.build_export_actions(
                [first, second],
                tmp_path / "out",
                "flac",
                prefix_track_number=True,
            )

            self.assertEqual(actions[0].dest.name, "01 Artist - Alpha.flac")
            self.assertEqual(actions[1].dest.name, "02 Artist - Beta.flac")
            self.assertEqual(actions[0].track_number, 1)
            self.assertEqual(actions[1].track_number, 2)

    def test_source_folder_art_falls_back_to_parent_album_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            disc_dir = tmp_path / "Album (2021)" / "CD01"
            disc_dir.mkdir(parents=True)
            track = disc_dir / "01 Artist - Song.flac"
            track.write_bytes(b"x")
            cover = disc_dir.parent / "Folder.jpg"
            cover.write_bytes(b"jpg")

            self.assertEqual(module.source_folder_art(track), cover)

    def test_build_ffmetadata_lines_include_replaygain_and_picture(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp) / "Folder.jpg"
            art.write_bytes(b"jpg")

            lines = module.build_ffmetadata_lines(
                module.playlist_metadata_pairs(
                    "exyu",
                    "Tony Cetinski",
                    "Dom",
                    "Various Artists",
                    "playlist",
                ),
                module.ReplayGainResult(gain_db=-3.25, peak_linear=0.891234),
                art,
            )

            self.assertEqual(lines[0], ";FFMETADATA1")
            self.assertIn("ALBUM=exyu", lines)
            self.assertIn("ALBUMARTIST=Various Artists", lines)
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
            stale_audio = dest / "playlist-library-audio-abc.opus"
            stale_final = dest / "playlist-library-final-abc.opus"
            stale_meta = dest / "playlist-library-meta-abc.ffmeta"
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

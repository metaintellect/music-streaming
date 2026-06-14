import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "normalize-audio-library-tags.py"
SPEC = importlib.util.spec_from_file_location("normalize_audio_library_tags", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class NormalizeAudioLibraryTagsTest(unittest.TestCase):
    def setUp(self):
        self.logger = module.Logger()

    def test_parse_bucket_map_overrides_defaults(self):
        mapping = module.parse_bucket_map(["misc=Pop Rock", "exyu=ExYU"])

        self.assertEqual(mapping["misc"], "Pop Rock")
        self.assertEqual(mapping["exyu"], "ExYU")
        self.assertEqual(mapping["metal"], "Metal")

    def test_derive_bucket_and_artist_from_music_path(self):
        root = Path("/music")
        bucket, artist = module.derive_bucket_and_artist(
            Path("/music/exyu/Various/Paket aranzman/01.wav"),
            root,
        )

        self.assertEqual(bucket, "exyu")
        self.assertEqual(artist, "Various")

    def test_desired_compilation_fields_for_exyu_various(self):
        album_artist, compilation, update_album_artist = module.desired_compilation_fields("exyu", "Various")

        self.assertEqual(album_artist, "Various")
        self.assertEqual(compilation, "1")
        self.assertTrue(update_album_artist)

    def test_desired_compilation_fields_for_exyu_various_artists(self):
        album_artist, compilation, update_album_artist = module.desired_compilation_fields("exyu", "Various Artists")

        self.assertEqual(album_artist, "Various Artists")
        self.assertEqual(compilation, "1")
        self.assertTrue(update_album_artist)

    def test_desired_compilation_fields_for_non_various_artist(self):
        album_artist, compilation, update_album_artist = module.desired_compilation_fields("metal", "Death")

        self.assertIsNone(album_artist)
        self.assertIsNone(compilation)
        self.assertFalse(update_album_artist)

    def test_plan_updates_targets_genre_and_compilation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            track = root / "exyu" / "Various" / "Paket aranzman" / "01 Song.wav"
            track.parent.mkdir(parents=True)
            track.write_bytes(b"fake")

            with mock.patch.object(
                module,
                "ffprobe_tags",
                return_value=module.AudioTags(
                    genre="JPop",
                    album_artist="Various Artists",
                    compilation=None,
                    style="Zabavni",
                ),
            ):
                planned = module.plan_updates(root, {"exyu"}, set(), module.DEFAULT_BUCKET_MAP, True, self.logger)

        self.assertEqual(len(planned), 1)
        update = planned[0]
        self.assertEqual(update.target_genre, "ExYU")
        self.assertEqual(update.target_album_artist, "Various")
        self.assertEqual(update.target_compilation, "1")

    def test_plan_updates_removes_compilation_for_non_various_album(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            track = root / "metal" / "Death" / "Human" / "01 Flattening of Emotions.flac"
            track.parent.mkdir(parents=True)
            track.write_bytes(b"fake")

            with mock.patch.object(
                module,
                "ffprobe_tags",
                return_value=module.AudioTags(
                    genre="Metal",
                    album_artist="Death",
                    compilation="1",
                    style=None,
                ),
            ):
                planned = module.plan_updates(root, {"metal"}, set(), module.DEFAULT_BUCKET_MAP, True, self.logger)

        self.assertEqual(len(planned), 1)
        update = planned[0]
        self.assertEqual(update.target_genre, "Metal")
        self.assertEqual(update.target_album_artist, "Death")
        self.assertIsNone(update.target_compilation)

    def test_ffprobe_tag_parsing_is_case_insensitive(self):
        payload = {
            "format": {
                "tags": {
                    "GENRE": "Pop Rock",
                    "ALBUMARTIST": "Various Artists",
                    "COMPILATION": "1",
                    "STYLE": "Adult Contemporary",
                }
            }
        }

        completed = mock.Mock(stdout=__import__("json").dumps(payload))
        with mock.patch.object(module, "run", return_value=completed):
            tags = module.ffprobe_tags(Path("/tmp/test.flac"))

        self.assertEqual(tags.genre, "Pop Rock")
        self.assertEqual(tags.album_artist, "Various Artists")
        self.assertEqual(tags.compilation, "1")
        self.assertEqual(tags.style, "Adult Contemporary")

    def test_plan_updates_can_filter_by_artist_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            keep = root / "misc" / "Various Artists" / "NOW - Yearbook 1990" / "CD01" / "01 Song.wav"
            skip = root / "misc" / "Abba" / "Gold" / "01 Dancing Queen.flac"
            keep.parent.mkdir(parents=True)
            skip.parent.mkdir(parents=True)
            keep.write_bytes(b"fake")
            skip.write_bytes(b"fake")

            with mock.patch.object(
                module,
                "ffprobe_tags",
                side_effect=[
                    module.AudioTags(genre="Pop", album_artist=None, compilation=None, style=None),
                    module.AudioTags(genre="Pop", album_artist=None, compilation=None, style=None),
                ],
            ):
                planned = module.plan_updates(
                    root,
                    {"misc"},
                    {"various artists"},
                    module.DEFAULT_BUCKET_MAP,
                    True,
                    self.logger,
                )

        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0].artist_folder, "Various Artists")

    def test_plan_updates_skips_genre_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            track = root / "misc" / "Various Artists" / "NOW - Yearbook 1990" / "CD01" / "01 Song.wav"
            track.parent.mkdir(parents=True)
            track.write_bytes(b"fake")

            with mock.patch.object(
                module,
                "ffprobe_tags",
                return_value=module.AudioTags(
                    genre="Pop Rock",
                    album_artist=None,
                    compilation=None,
                    style=None,
                ),
            ):
                planned = module.plan_updates(
                    root,
                    {"misc"},
                    {"various artists"},
                    module.DEFAULT_BUCKET_MAP,
                    False,
                    self.logger,
                )

        self.assertEqual(len(planned), 1)
        self.assertIsNone(planned[0].target_genre)
        self.assertEqual(planned[0].target_album_artist, "Various Artists")


if __name__ == "__main__":
    unittest.main()

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export-playlist-to-csv.py"
SPEC = importlib.util.spec_from_file_location("export_playlist_to_csv", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ExportPlaylistToCsvTest(unittest.TestCase):
    def test_decode_playlist_path_maps_unc_share_to_music_root(self):
        playlist = Path("/tmp/exyu.m3u")
        result = module.decode_playlist_path(
            r"\\192.168.100.83\xnas\music\exyu\Artist\Album\01 Artist - Song.flac",
            playlist,
        )

        self.assertEqual(result, Path("/music/exyu/Artist/Album/01 Artist - Song.flac"))

    def test_decode_playlist_path_strips_mount_prefix_before_music(self):
        playlist = Path("/tmp/exyu.m3u")
        result = module.decode_playlist_path(
            "/Volumes/xnas/music/exyu/Artist/Album/01 Artist - Song.flac",
            playlist,
        )

        self.assertEqual(result, Path("/music/exyu/Artist/Album/01 Artist - Song.flac"))

    def test_parse_artist_song_strips_track_number(self):
        artist, song = module.parse_artist_song("01 Artist - Song Title.flac")

        self.assertEqual(artist, "Artist")
        self.assertEqual(song, "Song Title")

    def test_parse_album_year_extracts_album_and_year(self):
        album, year = module.parse_album_year(
            Path("/mnt/nas/music/exyu/Artist/Album Title (1999)/01 Artist - Song.flac")
        )

        self.assertEqual(album, "Album Title")
        self.assertEqual(year, "1999")

    def test_parse_album_year_uses_parent_of_disc_folder(self):
        album, year = module.parse_album_year(
            Path("/mnt/nas/music/exyu/Artist/Zlatna Kolekcija (2005)/CD01/01 Artist - Song.flac")
        )

        self.assertEqual(album, "Zlatna Kolekcija")
        self.assertEqual(year, "2005")

    def test_playlist_rows_keep_filename_and_parent_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            playlist = tmp_path / "easy.m3u"
            playlist.write_text(
                "\\\\192.168.100.83\\xnas\\music\\misc\\Artist\\Album\\01 Artist - Song.flac\n",
                encoding="utf-8",
            )

            rows = module.playlist_rows(playlist)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].artist, "Artist")
            self.assertEqual(rows[0].song, "Song")
            self.assertEqual(rows[0].album, "Album")
            self.assertEqual(rows[0].year, "")
            self.assertEqual(rows[0].filename, "01 Artist - Song.flac")
            self.assertEqual(rows[0].path, "/music/misc/Artist/Album")

    def test_playlist_rows_are_sorted_by_artist_then_song(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            playlist = tmp_path / "easy.m3u"
            playlist.write_text(
                "\\\\192.168.100.83\\xnas\\music\\misc\\B Artist\\Album\\01 B Artist - Zebra.flac\n"
                "\\\\192.168.100.83\\xnas\\music\\misc\\A Artist\\Album\\01 A Artist - Alpha.flac\n",
                encoding="utf-8",
            )

            rows = module.playlist_rows(playlist)

            self.assertEqual([row.artist for row in rows], ["A Artist", "B Artist"])
            self.assertEqual([row.song for row in rows], ["Alpha", "Zebra"])

    def test_write_csv_writes_expected_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "easy.csv"
            rows = [
                module.PlaylistRow(
                    artist="Artist",
                    song="Song",
                    album="Album",
                    year="1999",
                    filename="01 Artist - Song.flac",
                    path="/music/misc/Artist/Album",
                )
            ]

            module.write_csv(rows, output)

            with output.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                loaded = list(reader)

            self.assertEqual(reader.fieldnames, ["artist", "song", "album", "year", "filename", "path"])
            self.assertEqual(
                loaded,
                [
                    {
                        "artist": "Artist",
                        "song": "Song",
                        "album": "Album",
                        "year": "1999",
                        "filename": "01 Artist - Song.flac",
                        "path": "/music/misc/Artist/Album",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()

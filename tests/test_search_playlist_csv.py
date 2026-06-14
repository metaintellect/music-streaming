import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "search-playlist-csv.py"
SPEC = importlib.util.spec_from_file_location("search_playlist_csv", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class SearchPlaylistCsvTest(unittest.TestCase):
    def test_resolve_csv_path_defaults_to_playlist_name_in_dir(self):
        result = module.resolve_csv_path("exyu", Path("/Users/x/Documents/playlists"), None)

        self.assertEqual(result, Path("/Users/x/Documents/playlists/exyu.csv"))

    def test_search_rows_matches_artist_and_song_case_insensitively(self):
        rows = [
            module.PlaylistMatch(
                artist="Mariah Carey",
                song="Emotions",
                filename="Mariah Carey - Emotions.flac",
                path="/mnt/nas/music/misc/Mariah Carey",
            ),
            module.PlaylistMatch(
                artist="Simply Red",
                song="Stars",
                filename="Simply Red - Stars.flac",
                path="/mnt/nas/music/misc/Simply Red",
            ),
        ]

        matches = module.search_rows(rows, "mariah emotions")

        self.assertEqual(matches, [rows[0]])

    def test_load_rows_reads_csv_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "easy.csv"
            csv_path.write_text(
                "artist,song,filename,path\nArtist,Song,01 Artist - Song.flac,/mnt/nas/music/Artist/Album\n",
                encoding="utf-8",
            )

            rows = module.load_rows(csv_path)

            self.assertEqual(
                rows,
                [
                    module.PlaylistMatch(
                        artist="Artist",
                        song="Song",
                        filename="01 Artist - Song.flac",
                        path="/mnt/nas/music/Artist/Album",
                    )
                ],
            )

    def test_format_matches_aligns_song_column(self):
        rows = [
            module.PlaylistMatch(
                artist="Tony Cetinski",
                song="Dom",
                filename="01 Tony Cetinski - Dom.flac",
                path="/music/exyu/Tony Cetinski/Prah I Pepeo (1997)",
            ),
            module.PlaylistMatch(
                artist="Tony Cetinski",
                song="Neka Nocas Dodju Svi (Live)",
                filename="04 Tony Cetinski - Neka Nocas Dodju Svi (Live).flac",
                path="/music/exyu/Tony Cetinski/Prah I Pepeo (1997)",
            ),
        ]

        lines = module.format_matches(rows)

        self.assertEqual(
            lines,
            [
                "Tony Cetinski | Dom                         | 01 Tony Cetinski - Dom.flac | /music/exyu/Tony Cetinski/Prah I Pepeo (1997)",
                "Tony Cetinski | Neka Nocas Dodju Svi (Live) | 04 Tony Cetinski - Neka Nocas Dodju Svi (Live).flac | /music/exyu/Tony Cetinski/Prah I Pepeo (1997)",
            ],
        )


if __name__ == "__main__":
    unittest.main()

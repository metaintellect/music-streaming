import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openpyxl import Workbook


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "roon-excel-to-plex-playlist.py"
SPEC = importlib.util.spec_from_file_location("roon_excel_to_plex_playlist", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class RoonExcelToPlexPlaylistTest(unittest.TestCase):
    def make_workbook(self, path: Path) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Tracks"
        sheet.append(["Title", "Path"])
        sheet.append(["First", r"\\192.168.100.83\xnas\music\a.flac"])
        sheet.append(["Blank", None])
        sheet.append(["Second", r"\\192.168.100.83\xnas\music\b.flac"])
        workbook.save(path)

    def test_parse_roon_excel_reads_path_column_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "playlist.xlsx"
            self.make_workbook(xlsx)

            parsed = module.parse_roon_excel(xlsx)

            self.assertEqual(parsed.tracks_read, 3)
            self.assertEqual(parsed.blank_paths, 1)
            self.assertEqual(
                parsed.paths,
                [
                    r"\\192.168.100.83\xnas\music\a.flac",
                    r"\\192.168.100.83\xnas\music\b.flac",
                ],
            )

    def test_write_m3u_preserves_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "playlist.m3u"

            module.write_m3u(output, ["one.flac", "two.flac"])

            self.assertEqual(output.read_text(encoding="utf-8"), "one.flac\ntwo.flac\n")

    def test_build_plex_url_encodes_unc_path(self):
        url = module.build_plex_url(
            "http://server:32400/",
            "/playlists/upload",
            {
                "sectionID": "1",
                "path": r"\\192.168.100.83\xnas\playlists\exyu.m3u",
                "X-Plex-Token": "secret",
            },
        )

        self.assertIn("sectionID=1", url)
        self.assertIn("path=%5C%5C192.168.100.83%5Cxnas%5Cplaylists%5Cexyu.m3u", url)
        self.assertIn("X-Plex-Token=secret", url)

    def test_upload_playlist_posts_to_plex(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b"<MediaContainer />"

        with mock.patch.object(module.urllib.request, "urlopen", return_value=Response()) as urlopen:
            status, body = module.upload_playlist(
                "http://server:32400",
                "secret",
                "1",
                r"\\192.168.100.83\xnas\playlists\exyu.m3u",
                force=True,
                timeout=20,
            )

        self.assertEqual(status, 200)
        self.assertEqual(body, "<MediaContainer />")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertIn("force=1", request.full_url)


if __name__ == "__main__":
    unittest.main()

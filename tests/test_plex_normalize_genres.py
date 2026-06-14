import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "plex-normalize-genres.py"
SPEC = importlib.util.spec_from_file_location("plex_normalize_genres", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class PlexNormalizeGenresTest(unittest.TestCase):
    def test_parse_bucket_map_overrides_defaults(self):
        mapping = module.parse_bucket_map(["misc=Pop Rock", "metal=Metal"])

        self.assertEqual(mapping["misc"], "Pop Rock")
        self.assertEqual(mapping["metal"], "Metal")
        self.assertEqual(mapping["jazz"], "Jazz")
        self.assertEqual(mapping["esoteric"], "Esoteric")
        self.assertEqual(mapping["esoteric-flac"], "Esoteric")
        self.assertEqual(mapping["exyu"], "ExYU")

    def test_derive_bucket_matches_longest_library_root(self):
        bucket = module.derive_bucket(
            r"\\192.168.100.83\xnas\music\Metal\Death\Human\01.wav",
            (
                r"\\192.168.100.83\xnas",
                r"\\192.168.100.83\xnas\music",
            ),
        )

        self.assertEqual(bucket, "metal")

    def test_derive_bucket_returns_none_outside_library_root(self):
        bucket = module.derive_bucket(
            r"\\192.168.100.83\other\music\Metal\Death\Human\01.wav",
            (r"\\192.168.100.83\xnas\music",),
        )

        self.assertIsNone(bucket)

    def test_build_plex_url_encodes_genre_update(self):
        url = module.build_plex_url(
            "http://server:32400/",
            "/library/sections/5/all",
            {
                "type": 9,
                "id": "123",
                "genre[0].tag.tag": "Pop Rock",
                "genre.locked": 1,
                "X-Plex-Token": "secret",
            },
        )

        self.assertIn("type=9", url)
        self.assertIn("id=123", url)
        self.assertIn("genre%5B0%5D.tag.tag=Pop+Rock", url)
        self.assertIn("genre.locked=1", url)
        self.assertIn("X-Plex-Token=secret", url)


if __name__ == "__main__":
    unittest.main()

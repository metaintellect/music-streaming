import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fix-audio-metadata-from-filename.py"
SPEC = importlib.util.spec_from_file_location("fix_audio_metadata_from_filename", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class FixAudioMetadataFromFilenameTest(unittest.TestCase):
    def test_contains_suspicious_text_detects_mojibake_markers(self):
        self.assertTrue(module.contains_suspicious_text("Jedna �ena plava"))
        self.assertTrue(module.contains_suspicious_text("Dal' se sjeti"))
        self.assertFalse(module.contains_suspicious_text("Jedna zena plava"))

    def test_derive_title_from_filename_strips_track_and_artist_prefix(self):
        title = module.derive_title_from_filename(
            Path("01 Mix - Sve Su Se Laste - Srce Ti Je Kamen.wav")
        )
        self.assertEqual(title, "Sve Su Se Laste - Srce Ti Je Kamen")

    def test_derive_title_from_filename_preserves_plain_stem_without_prefix(self):
        title = module.derive_title_from_filename(Path("03 Tuzna Su Zelena Polja.wav"))
        self.assertEqual(title, "Tuzna Su Zelena Polja")


if __name__ == "__main__":
    unittest.main()

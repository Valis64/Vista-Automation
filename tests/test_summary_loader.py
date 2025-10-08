import json
import tempfile
import unittest
from pathlib import Path

from order_gui import apply_summary_overrides, load_flat_summary_artifact


class SummaryLoaderTest(unittest.TestCase):
    def test_summary_override_prefers_recorded_flat(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "last_run.json"
            summary = {
                "generated_at": "2024-05-01T12:00:00Z",
                "pairs": [
                    {
                        "pair": 1,
                        "flat": "C:/print/123_flat_Lam.pdf",
                        "art_path": r"C:\\Art\\Piece.ai",
                    }
                ],
            }
            path.write_text(json.dumps(summary), encoding="utf-8")

            entries = load_flat_summary_artifact(path)
            guess = [
                (
                    "C:/print/123_flat_guess.pdf",
                    "ORDER-1",
                    1,
                    "ART123",
                    "Glue",
                    "TEMPLATE",
                    "Laminate",
                    r"C:\\Art\\Piece.ai",
                )
            ]
            pairs = [0]

            updated = apply_summary_overrides(guess, pairs, entries)
            self.assertEqual(updated[0][0], "C:/print/123_flat_Lam.pdf")

    def test_summary_override_retains_guess_when_missing(self):
        entries = []
        guess = [
            (
                "C:/print/guess.pdf",
                "ORDER-2",
                1,
                "ART999",
                "",
                "TEMP",
                "",
                r"C:\\Art\\Missing.ai",
            )
        ]
        pairs = [0]
        updated = apply_summary_overrides(guess, pairs, entries)
        self.assertEqual(updated[0][0], "C:/print/guess.pdf")


if __name__ == "__main__":
    unittest.main()

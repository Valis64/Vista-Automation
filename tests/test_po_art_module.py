import os
import tempfile

from utils.po_art import resolve_paired_page_art


class TestPoArtModule:
    def _context(self, order_id: str, month_root: str, art_id: str = "", **extra: object) -> dict:
        ctx = {
            "order_id": order_id,
            "month_root": month_root,
            "art_id": art_id,
            "art_root": "",
            "art_path": "",
            "template": "",
        }
        ctx.update(extra)
        return ctx

    def test_base_and_mate_detected_from_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "12001"
            art_id = "PAIR12001"
            art_folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(art_folder, exist_ok=True)
            page1 = os.path.join(art_folder, f"{art_id}_page1.pdf")
            page2 = os.path.join(art_folder, f"{art_id}_page2.pdf")
            for path in (page1, page2):
                with open(path, "w", encoding="utf-8"):
                    pass

            entries = [
                {"template": "PO10", "art_path": ""},
                {"template": "PO10B", "art_path": ""},
            ]
            contexts = [
                self._context(order_id, tmp, art_id),
                self._context(order_id, tmp, art_id),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            assert assignments[0] == page1
            assert assignments[1] == page2
            assert not skips
            assert not skip_reasons
            assert any("Resolved zip folder" in msg for msg in logs)

    def test_folder_resolution_uses_search_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "12002"
            art_id = "PAIRSEARCH"
            art_folder = os.path.join(tmp, "search", art_id)
            os.makedirs(art_folder, exist_ok=True)
            page1 = os.path.join(art_folder, "page1.pdf")
            page2 = os.path.join(art_folder, "page2.pdf")
            for path in (page1, page2):
                with open(path, "w", encoding="utf-8"):
                    pass

            entries = [
                {"template": "PO11", "art_path": ""},
                {"template": "PO11B", "art_path": ""},
            ]
            contexts = [
                self._context(order_id, tmp, art_id, search_dirs=[os.path.join(tmp, "search")]),
                self._context(order_id, tmp, art_id),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            assert assignments[0] == page1
            assert assignments[1] == page2
            assert not skips
            assert not skip_reasons

    def test_fallbacks_and_skip_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "12003"
            art_id = "PAIRFALL"
            base_art = os.path.join(tmp, f"{art_id}.pdf")
            with open(base_art, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO12", "art_path": base_art},
                {"template": "PO12B", "art_path": ""},
            ]
            contexts = [
                self._context(order_id, tmp, art_id, art_path=base_art),
                self._context(order_id, tmp, art_id),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            assert assignments[0] == base_art
            assert 1 in skips
            assert skip_reasons.get(1) == "Missing extracted PO art"
            assert any("Using standard art" in msg for msg in logs)

    def test_missing_art_marks_both(self):
        entries = [
            {"template": "PO13", "art_path": ""},
            {"template": "PO13B", "art_path": ""},
        ]
        contexts = [
            self._context("12004", ""),
            self._context("12004", ""),
        ]
        logs: list[str] = []

        assignments, skips, skip_reasons, _ = resolve_paired_page_art(
            entries, contexts, logs.append
        )

        assert not assignments
        assert skips == {0, 1}
        assert skip_reasons == {0: "No PO art found", 1: "No PO art found"}
        assert any("could not locate extracted folder" in msg for msg in logs)

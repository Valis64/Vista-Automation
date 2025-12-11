"""Helpers for resolving paired-page PO artwork files."""

from __future__ import annotations

import os
import traceback
from typing import Callable, Sequence

import fitz


__all__ = ["resolve_paired_page_art"]


def _collect_search_dirs(ctx: dict) -> list[str]:
    dirs: list[str] = []
    art_path = ctx.get("art_path") or ""
    if art_path:
        if os.path.isdir(art_path):
            dirs.append(art_path)
        else:
            parent = os.path.dirname(art_path)
            if parent:
                dirs.append(parent)
    art_root = ctx.get("art_root") or ""
    if art_root:
        dirs.append(art_root)
    month_root = ctx.get("month_root") or ""
    order_id = ctx.get("order_id") or ""
    if month_root and order_id:
        dirs.append(os.path.join(month_root, str(order_id), "art"))
    extra = ctx.get("search_dirs")
    if isinstance(extra, (list, tuple, set)):
        dirs.extend(str(d) for d in extra if d)
    elif extra:
        dirs.append(str(extra))
    seen: set[str] = set()
    ordered: list[str] = []
    for path in dirs:
        norm = os.path.abspath(path)
        if norm in seen:
            continue
        seen.add(norm)
        ordered.append(path)
    return ordered


def _pdf_page_count(path: str) -> int | None:
    if not path or not path.lower().endswith(".pdf"):
        return None
    doc = None
    try:
        doc = fitz.open(path)
        return doc.page_count
    except Exception:
        return None
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                traceback.print_exc()


def _get_find_art_file() -> Callable[..., str]:
    # Lazy import to avoid circular dependency with order_gui.
    from order_gui import find_art_file  # type: ignore

    return find_art_file


def _resolve_standard_art(
    entries: Sequence[dict],
    contexts: Sequence[dict],
    limit: int,
    idx: int | None,
) -> str:
    if idx is None or idx >= limit:
        return ""
    ctx = contexts[idx]
    entry = entries[idx] if idx < len(entries) else {}
    art_path = entry.get("art_path") or ctx.get("art_path") or ""
    if art_path:
        return art_path
    find_art_file = _get_find_art_file()
    art_root = ctx.get("art_root") or ""
    art_id = str(ctx.get("art_id") or "")
    month_root = ctx.get("month_root") or ""
    order_id = ctx.get("order_id") or ""
    name_hint = str(entry.get("template") or ctx.get("template") or "")
    return find_art_file(art_root, art_id, month_root, order_id, name_hint)


def _find_page(folder: str, number: int, stems: Sequence[str]) -> str:
    suffix = f"_page{number}.pdf"
    suffix_l = suffix.lower()
    legacy = f"page{number}.pdf"
    legacy_l = legacy.lower()
    stem_set = [s.lower() for s in stems if s]
    candidates: list[tuple[int, str]] = []
    try:
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            low = name.lower()
            if low == legacy_l:
                candidates.append((2, path))
                continue
            if not low.endswith(suffix_l):
                continue
            base = low[: -len(suffix_l)]
            priority = 1
            if stem_set:
                if base in stem_set:
                    priority = 0
                elif any(base.endswith(stem) or stem.endswith(base) for stem in stem_set):
                    priority = 1
                else:
                    priority = 1
            candidates.append((priority, path))
    except Exception:
        return ""
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (item[0], item[1].lower()))
    return candidates[0][1]


def _has_page(folder: str, stems: Sequence[str]) -> bool:
    return bool(_find_page(folder, 1, stems) or _find_page(folder, 2, stems))


def _locate_folder(
    base_code: str, entries: Sequence[dict], contexts: Sequence[dict], limit: int, indices: list[int], stems: list[str]
) -> str:
    base_lower = base_code.lower()
    for idx in indices:
        if idx >= limit:
            continue
        ctx = contexts[idx]
        entry = entries[idx] if idx < len(entries) else {}
        art_path = ctx.get("art_path") or entry.get("art_path") or ""
        art_id = str(ctx.get("art_id") or "")
        art_id_l = art_id.lower()
        if art_path:
            if os.path.isdir(art_path) and _has_page(art_path, stems):
                return art_path
            if os.path.isfile(art_path):
                parent = os.path.dirname(art_path)
                if os.path.isdir(parent) and _has_page(parent, stems):
                    return parent
        for root in _collect_search_dirs(ctx):
            if not os.path.isdir(root):
                continue
            root_name = os.path.basename(root.rstrip(os.sep)).lower()
            if art_id_l and art_id_l in root_name and _has_page(root, stems):
                return root
            if base_lower and base_lower in root_name and _has_page(root, stems):
                return root
            try:
                for name in os.listdir(root):
                    candidate = os.path.join(root, name)
                    if not os.path.isdir(candidate):
                        continue
                    low = name.lower()
                    if art_id_l and art_id_l in low and _has_page(candidate, stems):
                        return candidate
                    if base_lower in low and _has_page(candidate, stems):
                        return candidate
            except Exception:
                continue
    return ""


def _build_pair_map(entries: Sequence[dict], limit: int) -> dict[str, dict[str, int | None]]:
    pair_map: dict[str, dict[str, int | None]] = {}
    for idx in range(limit):
        template = str(entries[idx].get("template", "") or "").strip().upper()
        if not template.startswith("PO") or template.startswith("POB"):
            continue
        is_mate = template.endswith("B") and len(template) > 1
        base_code = template[:-1] if is_mate else template
        info = pair_map.setdefault(base_code, {"base": None, "mate": None})
        if is_mate:
            if info.get("mate") is None:
                info["mate"] = idx
        else:
            if info.get("base") is None:
                info["base"] = idx
    return pair_map


def resolve_paired_page_art(
    entries: Sequence[dict],
    contexts: Sequence[dict],
    logger: Callable[[str], None],
) -> tuple[dict[int, str], set[int], dict[int, str]]:
    """Assign PAGE1/PAGE2 files from extracted ZIP folders to P templates."""

    assignments: dict[int, str] = {}
    skips: set[int] = set()
    skip_reasons: dict[int, str] = {}

    def mark_skip(idx: int | None, reason: str) -> None:
        if idx is None:
            return
        skips.add(idx)
        skip_reasons.setdefault(idx, reason)

    if logger is None:
        logger = lambda _: None  # type: ignore[assignment]

    limit = min(len(entries), len(contexts))
    if limit == 0:
        return assignments, skips, skip_reasons

    pair_map = _build_pair_map(entries, limit)

    for base_code, info in pair_map.items():
        base_idx = info.get("base")
        mate_idx = info.get("mate")
        mate_template = (
            entries[mate_idx].get("template", "")
            if mate_idx is not None and mate_idx < len(entries)
            else ""
        )
        mate_label = mate_template or "missing"
        if mate_idx is None:
            logger(
                f"Warning: PO pair {base_code} missing mate template; expected {base_code}B."
            )
        indices: list[int] = []
        if mate_idx is not None:
            indices.append(mate_idx)
        if base_idx is not None:
            indices.append(base_idx)
        if not indices:
            continue
        stems: list[str] = []
        seen_stems: set[str] = set()
        for idx in indices:
            if idx >= limit:
                continue
            ctx = contexts[idx]
            entry = entries[idx] if idx < len(entries) else {}
            art_id = str(ctx.get("art_id") or entry.get("art_id") or "")
            if art_id and art_id.lower() not in seen_stems:
                stems.append(art_id)
                seen_stems.add(art_id.lower())
            for path in (
                ctx.get("art_path") or "",
                entry.get("art_path") if idx < len(entries) else "",
            ):
                if not path:
                    continue
                base_name = os.path.basename(path.rstrip(os.sep))
                stem, _ = os.path.splitext(base_name)
                stem_l = stem.lower()
                if stem and stem_l not in seen_stems:
                    stems.append(stem)
                    seen_stems.add(stem_l)
        if base_code and base_code.lower() not in seen_stems:
            stems.append(base_code)
            seen_stems.add(base_code.lower())
        art_id = ""
        for idx in indices:
            if idx >= limit:
                continue
            art_id = str(contexts[idx].get("art_id") or art_id)
            if art_id:
                break
        folder = _locate_folder(base_code, entries, contexts, limit, indices, stems)
        page1 = page2 = ""
        if folder:
            logger(
                f"Resolved zip folder for PO pair {base_code}: {folder} (art {art_id or 'unknown'}, mate {mate_label})."
            )
            page1 = _find_page(folder, 1, stems)
            page2 = _find_page(folder, 2, stems)

        fallback_art = _resolve_standard_art(entries, contexts, limit, base_idx)
        base_art_path = fallback_art or ""
        mate_missing_second_page = False
        if mate_idx is not None and base_art_path:
            page_count = _pdf_page_count(base_art_path)
            if page_count is not None and page_count < 2:
                mate_missing_second_page = True
                logger(
                    f"Warning: base art {base_art_path} has only {page_count} page(s); skipping template {mate_label}."
                )
                mark_skip(mate_idx, "No page 2 art")

        if folder and page1:
            if base_idx is not None and base_idx < len(entries):
                assignments[base_idx] = page1
            if mate_idx is not None and mate_idx < len(entries):
                if mate_missing_second_page:
                    pass
                elif page2:
                    assignments[mate_idx] = page2
                else:
                    logger(
                        f"Warning: page2.pdf not found for {base_code} in {folder}; skipping template {entries[mate_idx].get('template', base_code + 'B')}."
                    )
                    mark_skip(mate_idx, "Missing page2.pdf")
        elif fallback_art and base_idx is not None and base_idx < len(entries):
            if folder and not page1:
                logger(
                    f"Warning: page1.pdf not found for {base_code} in {folder}; using standard art instead."
                )
            assignments[base_idx] = fallback_art
            logger(
                f"Using standard art for PO pair {base_code} because extracted pages are unavailable for mate {mate_label}."
            )
            if mate_idx is not None:
                mark_skip(mate_idx, "Missing extracted PO art")
        else:
            logger(
                f"Error: could not locate extracted folder for PO pair {base_code} (art {art_id or 'unknown'}, mate {mate_label})."
            )
            for idx in indices:
                mark_skip(idx, "No PO art found")

    return assignments, skips, skip_reasons

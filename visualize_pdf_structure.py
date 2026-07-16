#!/usr/bin/env python3
"""Visualize extracted PDF structure — regions, rows, and words.

Usage:
    python visualize_pdf_structure.py <path_to_pdf> [--dpi 150]

Renders each page with bounding boxes:
  - Green:  regions
  - Blue:   rows
  - Red:    words

Arrow keys ← → / PageUp PageDown to switch pages.
Buttons at the bottom: ◀ Prev | Page N/M | Next ▶
Close window to exit.
"""

import sys
import time
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.widgets import Button
from pdf2image import convert_from_path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from pagerlib.file_input import FileInput
from pagerlib.extractors.page_extractor import Images2RegionsExtractor
from pagerlib.dtypes import Page, Region, Row, Word


def collect_elements(page: Page):
    """Walk the page hierarchy and return (regions, rows, words) lists."""
    regions: list[Region] = []
    rows: list[Row] = []
    words: list[Word] = []

    for child in page.children:
        if isinstance(child, Region):
            regions.append(child)
            for row in child.children or []:
                if isinstance(row, Row):
                    rows.append(row)
                    for word in row.children or []:
                        if isinstance(word, Word):
                            words.append(word)

    return regions, rows, words


def draw_page(ax, page: Page, pil_image, page_label: str):
    """Render one page: background image + bounding boxes for regions/rows/words."""
    seg = page.segment
    pw, ph = seg.width, seg.height

    ax.clear()
    ax.imshow(pil_image, extent=(0, pw, ph, 0))

    regions, rows, words = collect_elements(page)

    # Regions — green, thick
    for region in regions:
        rs = region.segment
        ax.add_patch(Rectangle(
            (rs.x_top_left, rs.y_top_left),
            rs.width, rs.height,
            linewidth=2.0, edgecolor="#22aa22", facecolor="#22aa2218",
        ))
        # Label with region class if present
        label = region.data.get("label", "") if region.data else ""
        if label:
            ax.text(rs.x_top_left + 2, rs.y_top_left + rs.height - 2,
                    label, fontsize=7, color="#22aa22",
                    va="top", ha="left", fontfamily="monospace",
                    bbox=dict(facecolor="white", alpha=0.7, pad=1, edgecolor="none"))

    # Rows — blue, medium
    for row in rows:
        rs = row.segment
        ax.add_patch(Rectangle(
            (rs.x_top_left, rs.y_top_left),
            rs.width, rs.height,
            linewidth=1.2, edgecolor="#3388ff", facecolor="#3388ff14",
        ))

    # Words — red, thin
    for word in words:
        ws = word.segment
        ax.add_patch(Rectangle(
            (ws.x_top_left, ws.y_top_left),
            ws.width, ws.height,
            linewidth=0.5, edgecolor="#ff4433", facecolor="#ff443310",
        ))

    ax.set_title(page_label, fontsize=10, fontfamily="monospace")
    ax.set_xticks([])
    ax.set_yticks([])


def main():
    ap = argparse.ArgumentParser(description="Visualize PDF structure (regions, rows, words)")
    ap.add_argument("pdf_path", help="Path to the PDF file")
    ap.add_argument("--dpi", type=int, default=150, help="Render DPI (default 150)")
    ap.add_argument("--ocr-images", action="store_true",
                    help="Apply PDFIMGExtractor + Images2RegionsExtractor to OCR embedded images")
    args = ap.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.is_file():
        print(f"ERROR: {pdf_path} not found")
        sys.exit(1)

    print(f"Reading {pdf_path.name} …")
    t0 = time.monotonic()

    # ── Pipeline: read PDF into PageRDF ──
    prdf = FileInput()(str(pdf_path))

    # ── Optional: OCR embedded images ──
    if args.ocr_images:
        # from pagerlib.extractors.page_extractor import PDFIMGExtractor
        # print("  → PDFIMGExtractor: rendering pages as images …")
        # pdf_img_extr = PDFIMGExtractor()
        # pdf_img_extr.extract(prdf)
        
        print("  → Images2RegionsExtractor: OCR on embedded images …")
        img_extr = Images2RegionsExtractor()
        img_extr.extract(prdf)

    pages = prdf.data.get("pages", [])
    n_pages = len(pages)
    elapsed = time.monotonic() - t0

    # Count stats
    total_regions = 0
    total_rows = 0
    total_words = 0
    for p in pages:
        reg, rw, wd = collect_elements(p)
        total_regions += len(reg)
        total_rows += len(rw)
        total_words += len(wd)

    print(f"  {n_pages} page(s)  {total_regions} regions  {total_rows} rows  {total_words} words  "
          f"({elapsed:.1f}s)")

    # ── Render pages as background images ──
    print(f"Rendering pages at {args.dpi} DPI …")
    pil_pages = convert_from_path(str(pdf_path), dpi=args.dpi)

    # ── UI state ──
    state = {"idx": 0}

    fig = plt.figure(figsize=(14, 19))
    fig.canvas.manager.set_window_title(f"PDF Structure Visualizer — {pdf_path.name}")

    gs = fig.add_gridspec(10, 1, height_ratios=[1] * 9 + [0.15])
    ax = fig.add_subplot(gs[:9, 0])
    btn_area = fig.add_subplot(gs[9, 0])
    btn_area.set_facecolor("#f0f0f0")
    btn_area.set_xticks([])
    btn_area.set_yticks([])

    btn_prev_ax = fig.add_axes([0.32, 0.01, 0.10, 0.035])
    btn_label_ax = fig.add_axes([0.44, 0.01, 0.12, 0.035])
    btn_next_ax = fig.add_axes([0.58, 0.01, 0.10, 0.035])

    btn_prev = Button(btn_prev_ax, "◀  Prev")
    btn_next = Button(btn_next_ax, "Next  ▶")

    label_text = btn_label_ax.text(
        0.5, 0.5, "", ha="center", va="center",
        fontsize=10, fontfamily="monospace", transform=btn_label_ax.transAxes,
    )
    btn_label_ax.set_xticks([])
    btn_label_ax.set_yticks([])

    def redraw(idx):
        page = pages[idx]
        pil = pil_pages[idx] if idx < len(pil_pages) else None

        reg, rw, wd = collect_elements(page)
        page_label = (
            f"Page {idx + 1}/{n_pages}  |  "
            f"PDF: {pdf_path.name}  |  "
            f"Regions: {len(reg)}  |  "
            f"Rows: {len(rw)}  |  "
            f"Words: {len(wd)}  |  "
            f"Extraction: {elapsed:.1f}s"
        )
        draw_page(ax, page, pil, page_label)
        label_text.set_text(f"Page {idx + 1} / {n_pages}")
        fig.canvas.draw_idle()

    def go_next(_event=None):
        if state["idx"] < n_pages - 1:
            state["idx"] += 1
            redraw(state["idx"])

    def go_prev(_event=None):
        if state["idx"] > 0:
            state["idx"] -= 1
            redraw(state["idx"])

    btn_next.on_clicked(go_next)
    btn_prev.on_clicked(go_prev)

    def on_key(event):
        if event.key in ("right", "down", "pagedown"):
            go_next()
        elif event.key in ("left", "up", "pageup"):
            go_prev()
        elif event.key == "home":
            state["idx"] = 0
            redraw(state["idx"])
        elif event.key == "end":
            state["idx"] = n_pages - 1
            redraw(state["idx"])

    fig.canvas.mpl_connect("key_press_event", on_key)
    redraw(0)
    plt.subplots_adjust(left=0.02, right=0.98, top=0.97, bottom=0.06)
    plt.show()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Visualize extracted PDF structure — text rows and image regions.

Usage:
    python visualize_pdf.py <path_to_pdf> [--dpi 150]

Renders each page with bounding boxes:
  - Blue: text rows
  - Red:  image regions

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
from pagerlib.file_input.pdf_as_json_model.miner_pdf_model import MinerPDFModel


def main():
    ap = argparse.ArgumentParser(description="Visualize PDF extracted structure")
    ap.add_argument("pdf_path", help="Path to the PDF file")
    ap.add_argument("--dpi", type=int, default=150, help="Render DPI (default 150)")
    args = ap.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.is_file():
        print(f"ERROR: {pdf_path} not found")
        sys.exit(1)

    print(f"Extracting structure from {pdf_path.name} …")
    t0 = time.monotonic()
    model = MinerPDFModel()
    model.read_from_file(str(pdf_path))
    elapsed = time.monotonic() - t0

    pages_data = model.pdf_json["pages"]
    n_pages = len(pages_data)
    total_rows = sum(len(p["rows"]) for p in pages_data)
    total_images = sum(len(p["images"]) for p in pages_data)
    print(f"  {n_pages} page(s)  {total_rows} text rows  {total_images} image regions  "
          f"({elapsed:.1f}s)")

    print(f"Rendering pages at {args.dpi} DPI …")
    pil_pages = convert_from_path(str(pdf_path), dpi=args.dpi)

    state = {"idx": 0}

    fig = plt.figure(figsize=(14, 19))
    fig.canvas.manager.set_window_title(f"PDF Visualizer — {pdf_path.name}")

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

    def draw_page(idx):
        ax.clear()
        data = pages_data[idx]
        pw = data["width"]
        ph = data["height"]

        if idx < len(pil_pages):
            ax.imshow(pil_pages[idx], extent=(0, pw, ph, 0))
        else:
            ax.set_xlim(0, pw)
            ax.set_ylim(ph, 0)
            ax.set_facecolor("white")

        for row in data["rows"]:
            seg = row["segment"]
            ax.add_patch(Rectangle(
                (seg["x_top_left"], seg["y_top_left"]),
                seg["width"], seg["height"],
                linewidth=1, edgecolor="#3388ff", facecolor="#3388ff22",
            ))

        for img_el in data["images"]:
            seg = img_el["segment"]
            ax.add_patch(Rectangle(
                (seg["x_top_left"], seg["y_top_left"]),
                seg["width"], seg["height"],
                linewidth=1.5, edgecolor="#ff3333", facecolor="#ff333322",
            ))

        ax.set_title(
            f"Page {idx + 1}/{n_pages}  |  "
            f"PDF: {pdf_path.name}  |  "
            f"Rows: {len(data['rows'])}  |  "
            f"Images: {len(data['images'])}  |  "
            f"Extraction: {elapsed:.1f}s",
            fontsize=10, fontfamily="monospace",
        )
        ax.set_xticks([])
        ax.set_yticks([])
        label_text.set_text(f"Page {idx + 1} / {n_pages}")
        fig.canvas.draw_idle()

    def go_next(_event=None):
        if state["idx"] < n_pages - 1:
            state["idx"] += 1
            draw_page(state["idx"])

    def go_prev(_event=None):
        if state["idx"] > 0:
            state["idx"] -= 1
            draw_page(state["idx"])

    btn_next.on_clicked(go_next)
    btn_prev.on_clicked(go_prev)

    def on_key(event):
        if event.key in ("right", "down", "pagedown"):
            go_next()
        elif event.key in ("left", "up", "pageup"):
            go_prev()
        elif event.key == "home":
            state["idx"] = 0
            draw_page(state["idx"])
        elif event.key == "end":
            state["idx"] = n_pages - 1
            draw_page(state["idx"])

    fig.canvas.mpl_connect("key_press_event", on_key)
    draw_page(0)
    plt.subplots_adjust(left=0.02, right=0.98, top=0.97, bottom=0.06)
    plt.show()


if __name__ == "__main__":
    main()

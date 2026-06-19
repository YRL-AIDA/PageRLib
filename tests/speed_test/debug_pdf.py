"""Debug script for PDF processing with timing statistics.

Usage:
    python debug_pdf.py <path_to_pdf> [timeout_seconds]

The script processes a PDF in debug mode, prints timing for each phase
and statistics about extracted elements.  Kills itself after *timeout*
seconds (default 60).
"""

import sys
import signal
import time
from pathlib import Path

_TIMEOUT_DEFAULT = 60


def _on_timeout(_signum, _frame):
    print("\nTIMEOUT: processing exceeded limit")
    sys.exit(1)


def _print_stats(result):
    pages = result.get("pages", [])
    total_rows = 0
    total_images = 0
    for p in pages:
        pn = p.get("number", "?")
        pw = p.get("width", 0)
        ph = p.get("height", 0)
        nr = len(p.get("rows", []))
        ni = len(p.get("images", []))
        total_rows += nr
        total_images += ni
        print(f"  Page {pn}: {pw}x{ph}  rows={nr}  images={ni}")
    print(f"Total: {len(pages)} page(s)  rows={total_rows}  images={total_images}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {Path(__file__).name} <pdf_path> [timeout]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else _TIMEOUT_DEFAULT

    if not Path(pdf_path).is_file():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    signal.signal(signal.SIGALRM, _on_timeout)
    signal.alarm(timeout)

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

    from pagerlib.file_input.pdf_as_json_model.miner_pdf_model import MinerPDFModel

    print(f"Processing: {pdf_path}  (timeout={timeout}s)")

    t0 = time.monotonic()
    model = MinerPDFModel(conf={"debug_timing": True})
    model.read_from_file(pdf_path)
    elapsed = time.monotonic() - t0

    signal.alarm(0)
    _print_stats(model.pdf_json)
    print(f"Wall time: {elapsed:.3f}s")


if __name__ == "__main__":
    main()

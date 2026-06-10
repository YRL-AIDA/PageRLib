import subprocess
import sys
from pathlib import Path

import pytest


TEST_PDF = Path(__file__).parent / "PMC4395846_00011.pdf"
TIME_LIMIT_SEC = 30.0
HARD_TIMEOUT_SEC = TIME_LIMIT_SEC * 2


def _make_script(pdf_path):
    return f"""
import time
from pagerlib.file_input import FileInput
fi = FileInput()
start = time.monotonic()
result = fi({pdf_path!r})
elapsed = time.monotonic() - start
print(f"OK:{{elapsed:.3f}}")
"""


@pytest.mark.skipif(not TEST_PDF.is_file(), reason="test pdf not found")
def test_miner_pdf_processing_speed():
    script = _make_script(str(TEST_PDF))
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=HARD_TIMEOUT_SEC,
        cwd=Path(__file__).resolve().parents[2],
        env={**__import__("os").environ, "PYTHONPATH": "src"},
    )

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        pytest.fail(
            f"PDF processing failed (rc={proc.returncode}):\n"
            f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    stdout = proc.stdout.strip()
    assert stdout.startswith("OK:"), f"Unexpected output: {stdout}"
    elapsed = float(stdout.split(":")[1])
    assert elapsed < TIME_LIMIT_SEC, (
        f"PDF processing took {elapsed:.2f}s, exceeded limit of {TIME_LIMIT_SEC}s"
    )

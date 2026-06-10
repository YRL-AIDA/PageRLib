import subprocess
import sys
from pathlib import Path

import pytest


TEST_PDF = Path(__file__).parent / "PMC2532955_00002.pdf"


def _extract(pdf_path):
    script = f"""
import json
from pagerlib.file_input.pdf_as_json_model.miner_pdf_model.miner_pdf_model import PDFStructureExtractor
extractor = PDFStructureExtractor()
result = extractor.extract_from_path({str(pdf_path)!r})
print(json.dumps(result))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
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
    import json
    return json.loads(proc.stdout.strip())


@pytest.fixture(scope="module")
def extracted_data():
    return _extract(TEST_PDF)


class TestAllElementsExtraction:
    def test_document_structure(self, extracted_data):
        assert "document" in extracted_data
        assert "pages" in extracted_data
        assert len(extracted_data["pages"]) > 0
        assert extracted_data["document"] == str(TEST_PDF)

    def test_page_has_text(self, extracted_data):
        for page in extracted_data["pages"]:
            assert "rows" in page
            assert len(page["rows"]) > 0, (
                f"Page {page['number']} has no text rows, "
                f"but PDF is expected to contain text"
            )

    def test_page_has_images(self, extracted_data):
        for page in extracted_data["pages"]:
            assert "images" in page
            assert len(page["images"]) > 0, (
                f"Page {page['number']} has no images, "
                f"but PDF is expected to contain a block diagram"
            )

    def test_images_have_valid_segments(self, extracted_data):
        for page in extracted_data["pages"]:
            for i, img in enumerate(page["images"]):
                seg = img["segment"]
                assert seg["width"] > 0, (
                    f"Image {i} on page {page['number']} has width <= 0"
                )
                assert seg["height"] > 0, (
                    f"Image {i} on page {page['number']} has height <= 0"
                )
                assert seg["x_top_left"] >= 0
                assert seg["y_top_left"] >= 0
                assert seg["x_top_left"] + seg["width"] <= page["width"] + 1
                assert seg["y_top_left"] + seg["height"] <= page["height"] + 1
                assert isinstance(img["text"], str)

    def test_text_rows_have_words(self, extracted_data):
        for page in extracted_data["pages"]:
            for row in page["rows"]:
                assert "words" in row
                assert len(row["words"]) > 0, (
                    f"Text row on page {page['number']} has no words: "
                    f"'{row.get('text', '')}'"
                )

    def test_block_diagram_extracted_as_image(self, extracted_data):
        page0 = extracted_data["pages"][0]
        diagram_images = [
            img for img in page0["images"]
            if img.get("image_name") is None
        ]
        assert len(diagram_images) > 0, (
            "Block diagram (paths/curves) was not extracted as an image. "
            f"Found {len(page0['images'])} images total, "
            f"but none without an image_name (path-derived images)"
        )

    def test_page_dimensions_positive(self, extracted_data):
        for page in extracted_data["pages"]:
            assert page["width"] > 0
            assert page["height"] > 0
            assert page["number"] >= 0

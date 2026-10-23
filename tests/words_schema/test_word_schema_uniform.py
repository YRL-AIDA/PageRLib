"""
Регрессионные тесты единой схемы слова (этап 2 «Word schema uniform»).

Контекст: KeyError 'font' в rows2regions.py (fix_row_this_image/get_rows) на
OCR-словах (data = {text, confidence}) при жёстком доступе w['data']['font'].

Тестируются:
  - fix_row_this_image без загрузки GNN-модели (self не используется);
  - нормализация Row.from_dict / _get_children_from_dict_list;
  - потребитель font: LogicalStructureExtractor._HeadingInfo._extract_font.

Запуск: PYTHONPATH=src pytest tests/words_schema/test_word_schema_uniform.py
"""
import pytest

from pagerlib.extractors.page_extractor.rows2regions.rows2regions import Rows2Regions
from pagerlib.dtypes.physical_elements.row import Row
from pagerlib.dtypes.physical_elements.word import Word
from pagerlib.dtypes.physical_elements.region import Region
from pagerlib.dtypes.physical_elements.font import Font
from pagerlib.extractors.document_extractor.logical_structure_extractor import _HeadingInfo

# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

OCR_WORD = {
    "segment": {"x_top_left": 10, "y_top_left": 10, "width": 100, "height": 20},
    "data": {"text": "hello", "confidence": 87.0},
}

PDF_WORD = {
    "segment": {"x_top_left": 10, "y_top_left": 10, "width": 100, "height": 20},
    "data": {"text": "Title", "font": {"fontname": "Times-Bold", "fontsize": 14, "is_normal": True}},
}

PDF_FONT = {"fontname": "Times-Bold", "fontsize": 14, "is_normal": True}

# Сегменты вне пересечения, чтобы текстовая строка не «слилась» с изображением.
TEXT_ROW_SEGMENT = {"x_top_left": 10, "y_top_left": 10, "width": 300, "height": 30}
IMAGE_ROW_SEGMENT = {"x_top_left": 500, "y_top_left": 500, "width": 50, "height": 50}


def _text_row(words):
    """Строка в схеме page_extract: {text, segment, words}."""
    return {"text": " ".join(w["data"].get("text", "") for w in words),
            "segment": TEXT_ROW_SEGMENT,
            "words": words}


def _image_row():
    """Строка-изображение без ключа 'words' (как в page_extract images)."""
    return {"text": "img", "segment": IMAGE_ROW_SEGMENT}


def _rows_with_words(result_rows):
    """Возвращает строки, у которых есть непустой список words."""
    return [r for r in result_rows if r.get("words")]


# ---------------------------------------------------------------------------
# 3.1 fix_row_this_image
# ---------------------------------------------------------------------------

class TestFixRowThisImage:

    def test_ocr_words_without_font_no_crash(self):
        """OCR-слова (нет font) + image_rows без 'words': без исключения,
        text сохранён, confidence сохранён, font не выдуман."""
        rows = [_text_row([OCR_WORD])]
        image_rows = [_image_row()]
        result = Rows2Regions.fix_row_this_image(None, rows, image_rows)

        text_rows = _rows_with_words(result)
        assert len(text_rows) == 1
        word = text_rows[0]["words"][0]
        assert word["data"]["text"] == "hello"
        assert word["data"]["confidence"] == 87.0
        assert "font" not in word["data"]

    def test_pdf_words_with_font_preserved(self):
        """PDF-слова (есть font): font сохраняется без изменений."""
        rows = [_text_row([PDF_WORD])]
        image_rows = [_image_row()]
        result = Rows2Regions.fix_row_this_image(None, rows, image_rows)

        text_rows = _rows_with_words(result)
        assert len(text_rows) == 1
        word = text_rows[0]["words"][0]
        assert word["data"]["text"] == "Title"
        assert word["data"]["font"] == PDF_FONT

    def test_mixed_pdf_and_ocr_words(self):
        """PDF- и OCR-слова в одном наборе строк — без падения, обе схемы живы."""
        rows = [_text_row([PDF_WORD]), _text_row([OCR_WORD])]
        image_rows = []
        result = Rows2Regions.fix_row_this_image(None, rows, image_rows)

        text_rows = _rows_with_words(result)
        assert len(text_rows) == 2
        fonts = [w["data"].get("font") for r in text_rows for w in r["words"]]
        assert PDF_FONT in fonts            # PDF-font сохранён
        assert None in fonts                # OCR-font не выдуман

    def test_image_rows_without_words(self):
        """image_rows без ключа 'words' не падают (дефолт [])."""
        rows = []
        image_rows = [_image_row(), _image_row()]
        result = Rows2Regions.fix_row_this_image(None, rows, image_rows)
        # Строки изображений остались в результате (без words)
        assert len(result) >= 1

    def test_empty_rows_and_image_rows(self):
        """Полностью пустой вход — без исключения."""
        result = Rows2Regions.fix_row_this_image(None, [], [])
        assert result == []


# ---------------------------------------------------------------------------
# 3.2 Нормализация Row.from_dict / _get_children_from_dict_list
# ---------------------------------------------------------------------------

class TestRowNormalization:

    @staticmethod
    def _from_dict_row(words):
        row = Row.get_none()
        row.from_dict({"segment": TEXT_ROW_SEGMENT, "words": words})
        return row

    def test_nested_data_with_font(self):
        """Вложенная схема {segment, data:{text, font}} → font в Word.data."""
        row = self._from_dict_row([PDF_WORD])
        word = row.children[0]
        assert word.data["text"] == "Title"
        assert word.data["font"] == PDF_FONT

    def test_nested_data_with_confidence(self):
        """Вложенная схема {segment, data:{text, confidence}} → confidence есть,
        font отсутствует, исключения нет."""
        row = self._from_dict_row([OCR_WORD])
        word = row.children[0]
        assert word.data["text"] == "hello"
        assert word.data["confidence"] == 87.0
        assert "font" not in word.data

    def test_flat_legacy_with_font(self):
        """Плоская legacy-схема {segment, text, font} → нормализуется."""
        flat = {"segment": OCR_WORD["segment"], "text": "Title", "font": PDF_FONT}
        row = self._from_dict_row([flat])
        word = row.children[0]
        assert word.data["text"] == "Title"
        assert word.data["font"] == PDF_FONT

    def test_raw_ocr_conf(self):
        """Сырая OCR-схема {segment, text, conf} → data['confidence'], font нет."""
        raw = {"segment": OCR_WORD["segment"], "text": "hello", "conf": 87.0}
        row = self._from_dict_row([raw])
        word = row.children[0]
        assert word.data["text"] == "hello"
        assert word.data["confidence"] == 87.0
        assert "font" not in word.data

    def test_word_confidence_property(self):
        """Word.confidence извлечён из data."""
        row = self._from_dict_row([OCR_WORD])
        assert row.children[0].confidence == 87.0


# ---------------------------------------------------------------------------
# 3.3 Потребитель font: LogicalStructureExtractor._HeadingInfo._extract_font
# ---------------------------------------------------------------------------

def _make_region_with_words(words):
    """Region с одной строкой, содержащей данные слова в нужной схеме."""
    word_objs = [
        Word(segment=w["segment"],
             data=dict(w.get("data", {"text": w.get("text", "")})))
        for w in words
    ]
    row = Row(children=word_objs, segment=TEXT_ROW_SEGMENT)
    return Region(children=[row], data={"label": "text"})


class TestExtractFont:

    def test_pdf_words_real_font(self):
        """PDF-слова → реальный шрифт из word.data['font']."""
        region = _make_region_with_words([PDF_WORD])
        font = _HeadingInfo._extract_font(region)
        assert isinstance(font, Font)
        assert font.size == 14
        assert font.width == 1.0       # Times-Bold
        assert font.italic == 0.0

    def test_ocr_words_font_defaults(self):
        """OCR-слова (нет font) → Font({}) с дефолтами, без исключения."""
        region = _make_region_with_words([OCR_WORD])
        font = _HeadingInfo._extract_font(region)
        assert isinstance(font, Font)
        assert font.size == -1
        assert font.width == 0.5
        assert font.italic == 0.0

    def test_region_without_children(self):
        """Регион без детей → Font({})."""
        region = Region(children=None, segment=TEXT_ROW_SEGMENT, data={"label": "figure"})
        font = _HeadingInfo._extract_font(region)
        assert isinstance(font, Font)
        assert font.size == -1
        assert font.width == 0.5
        assert font.italic == 0.0

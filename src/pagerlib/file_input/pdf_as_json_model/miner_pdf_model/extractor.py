import math
import logging
from typing import Dict, List

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.layout import LTTextLine, LTChar, LTImage, LTFigure, LTCurve, LAParams

from .aggregator import _FastPDFPageAggregator
from . import char_lines
from .text_extractor import TextExtractor
from .visual_extractor import VisualExtractor
from .merged_element import _PreMergedBox

logging.getLogger("pdfminer.pdfinterp").setLevel(logging.ERROR)


class PDFStructureExtractor:
    BASE_DPI = 72

    def __init__(self, laparams: LAParams = None, debug_curves: bool = False):
        self.laparams = laparams or LAParams(
            line_margin=0.5, word_margin=0.1, char_margin=2.0,
            boxes_flow=0.5, detect_vertical=True)
        self.debug_curves = debug_curves
        self.text = TextExtractor()
        self.visual = VisualExtractor(debug_curves=debug_curves)

    def extract_from_path(self, pdf_path: str) -> Dict:
        result = {"document": pdf_path, "pages": []}
        with open(pdf_path, 'rb') as fp:
            parser = PDFParser(fp)
            document = PDFDocument(parser)
            rsrcmgr = PDFResourceManager()
            device = _FastPDFPageAggregator(rsrcmgr, laparams=self.laparams)
            interpreter = PDFPageInterpreter(rsrcmgr, device)
            for page_num, page in enumerate(PDFPage.create_pages(document)):
                interpreter.process_page(page)
                path_bboxes = device.get_path_bboxes()
                figure_path_bboxes = device.get_figure_path_bboxes()
                device.clear_path_bboxes()
                page_layout = device.get_result()
                page_info = self._process_page(
                    page_layout, page_num, path_bboxes, figure_path_bboxes)
                result["pages"].append(page_info)
        return result

    def _process_page(self, page_layout, page_number: int,
                      path_bboxes=None, figure_path_bboxes=None) -> Dict:
        page_w = math.ceil(page_layout.width * self.BASE_DPI / 72)
        page_h = math.ceil(page_layout.height * self.BASE_DPI / 72)
        page_info = {"number": page_number, "width": page_w, "height": page_h,
                     "rows": [], "images": []}

        elements = []
        self._collect_elements(page_layout, elements, stop_types=LTFigure)

        skip_ids = self._build_figure_skip_ids(elements)
        text_lines, page_chars, visuals = self._classify_visual_elements(
            elements, skip_ids)

        self._add_path_visuals(visuals, path_bboxes, figure_path_bboxes,
                              page_w, page_h)

        if not text_lines and page_chars:
            text_lines = char_lines.chars_to_text_lines(page_chars)

        page_info["rows"] = self._extract_page_rows(text_lines, page_layout.height)
        page_info["images"] = self._extract_page_images(
            visuals, page_layout.height, page_w, page_h)

        page_info["rows"].sort(key=lambda x: x["segment"]["y_top_left"])
        page_info["images"].sort(key=lambda x: x["segment"]["y_top_left"])
        return page_info

    @staticmethod
    def _build_figure_skip_ids(elements):
        skip_ids = set()
        for element in elements:
            if isinstance(element, LTFigure):
                children = []
                PDFStructureExtractor._collect_elements(element, children)
                for c in children:
                    if isinstance(c, (LTImage, LTCurve)):
                        skip_ids.add(id(c))
        return skip_ids

    def _classify_visual_elements(self, elements, skip_ids):
        text_lines = []
        page_chars = []
        visuals = []
        for element in elements:
            if id(element) in skip_ids:
                continue
            if isinstance(element, LTTextLine):
                text_lines.append(element)
            elif isinstance(element, LTChar):
                page_chars.append(element)
            elif isinstance(element, LTImage):
                visuals.append(element)
            elif isinstance(element, LTFigure):
                figure_visuals = self.visual.extract_from_figure(element)
                visuals.extend(figure_visuals)
            elif isinstance(element, LTCurve):
                visuals.append(element)
        return text_lines, page_chars, visuals

    def _add_path_visuals(self, visuals, path_bboxes, figure_path_bboxes,
                         page_w, page_h):
        # Phase-1: grid BFS with small cell size for initial co-location groups.
        # Wrap in _PreMergedBox (padded in overlap merge,_MergedElement is not).
        if path_bboxes:
            merged = self.visual.merge_path_bboxes(
                path_bboxes, page_w, page_h, cell_size=4)
            for bbox in merged:
                visuals.append(_PreMergedBox(bbox))
        if figure_path_bboxes:
            for fbboxes in figure_path_bboxes.values():
                if not fbboxes:
                    continue
                merged = self.visual.merge_path_bboxes(
                    fbboxes, page_w, page_h, cell_size=4)
                for bbox in merged:
                    visuals.append(_PreMergedBox(bbox))

    def _extract_page_rows(self, text_lines, page_height):
        rows = []
        for text_line in text_lines:
            row_info = self.text.process_text_line(text_line, page_height)
            if (row_info and TextExtractor.is_correct_segment(row_info["segment"])
                    and len(row_info["words"]) != 0):
                rows.append(row_info)
        return self.text.merge_vertical_rows(rows)

    def _extract_page_images(self, visuals, page_height, page_w, page_h):
        merged = self.visual.merge_overlapping_images(visuals)
        result = []
        for elem in merged:
            image_info = self.visual.process_image(elem, page_height, page_w, page_h)
            if image_info and TextExtractor.is_correct_segment(image_info["segment"]):
                result.append(image_info)
        return result

    @staticmethod
    def _collect_elements(element, elements_list: List, stop_types=None):
        elements_list.append(element)
        if stop_types and isinstance(element, stop_types):
            return
        if hasattr(element, '_objs'):
            for child in element._objs:
                PDFStructureExtractor._collect_elements(
                    child, elements_list, stop_types)

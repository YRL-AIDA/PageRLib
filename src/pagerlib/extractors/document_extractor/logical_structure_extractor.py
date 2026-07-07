import re
from typing import List, Tuple
from pagerlib.dtypes import PageRDF, Section, Context
from pagerlib.dtypes import Image
from pagerlib.dtypes.physical_elements.font import Font

from .base_document_extractor import BaseDocumentExtractor

_NUMBERING_RE = re.compile(r'^\(?(\d+(?:\.\d+)*)[\.\)\s\-]')
_ROMAN_RE = re.compile(r'^([IVXLCDM]+|[ivxlcdm]+)\.\s')

SMALLER = -1
EQUAL = 0
LARGER = 1


class _HeadingInfo:
    __slots__ = ('text', 'font_size', 'is_bold', 'is_italic',
                 'numbering_depth', 'page_num', 'region')

    def __init__(self, region):
        self.text = region.text.strip() if region.text else ""
        self.region = region
        font = self._extract_font(region)
        self.font_size = font.size if font.size != -1 else 12.0
        self.is_bold = font.width > 0.8
        self.is_italic = font.italic > 0.8
        self.numbering_depth = self._detect_numbering(self.text)

    @staticmethod
    def _extract_font(region):
        if region.children is None:
            return Font({})
        for row in region.children:
            if row.children is None:
                continue
            for word in row.children:
                if word.data and "font" in word.data:
                    return Font(word.data["font"])
        for row in region.children:
            if row.children is None:
                continue
            for word in row.children:
                if word.data and word.data.get("text", "").strip():
                    return Font({})
        return Font({})

    @staticmethod
    def _detect_numbering(text: str) -> int:
        text = text.strip()
        m = _NUMBERING_RE.match(text)
        if m:
            return m.group(1).count('.') + 1
        m = _ROMAN_RE.match(text)
        if m:
            return 1
        return 0


def _compare_headings(h1: _HeadingInfo, h2: _HeadingInfo) -> int:
    if h1.font_size > 0 and h2.font_size > 0:
        ratio = h1.font_size / h2.font_size
        if ratio < 0.88:
            return SMALLER
        if ratio > 1.12:
            return LARGER

    nd1 = h1.numbering_depth
    nd2 = h2.numbering_depth
    if nd1 > 0 and nd2 > 0:
        if nd1 > nd2:
            return SMALLER
        if nd1 < nd2:
            return LARGER

    if h1.is_bold != h2.is_bold:
        if not h1.is_bold and h2.is_bold:
            return SMALLER
        if h1.is_bold and not h2.is_bold:
            return LARGER

    if h1.is_italic != h2.is_italic:
        if h1.is_italic and not h2.is_italic:
            return SMALLER
        if not h1.is_italic and h2.is_italic:
            return LARGER

    return EQUAL


class LogicalStructureExtractor(BaseDocumentExtractor):

    def document_extract(self, prdf: PageRDF):
        all_regions = self._collect_all_regions(prdf)
        if not all_regions:
            return []
        

        root = Section(title=None, level=0)
        stack: List[Tuple[Section, _HeadingInfo|None]] = [(root, None)]
        header_count = 0

        for region in all_regions:
            label = region.data.get("label", "") if region.data else ""

            if label != "header":
                current: Section = stack[-1][0]
                current.add_context(region)
                continue


            hi = _HeadingInfo(region)
            sec = Section(title=region, level=len(stack))
            header_count += 1

            while stack:
                if len(stack) == 1:
                    break
                if _compare_headings(hi, stack[-1][1]) == SMALLER:
                    break
                stack.pop()

            parent_sec: Section = stack[-1][0]
            parent_sec.children.append(sec)
            sec.level = parent_sec.level + 1
        
            stack.append((sec, hi))

        return root.children

    @staticmethod
    def _collect_all_regions(prdf: PageRDF) -> List[tuple]:
        regions = []
        pages = prdf.data.get("pages", [])
        for page in pages:
            if page.children is None:
                continue
            for region in page.children:
                if isinstance(region, Image):
                    continue
                regions.append(region)
        return regions

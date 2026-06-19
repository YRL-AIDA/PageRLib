import math
from typing import Dict, List

import numpy as np
import cv2
from pdfminer.layout import LTImage, LTFigure, LTCurve

from . import coordinate_utils as coord
from .merged_element import _MergedElement, _PreMergedBox
from .text_extractor import TextExtractor


class VisualExtractor:
    MORPH_SCALE = 2
    MORPH_DILATE_RADIUS = 10
    MORPH_MIN_AREA = 500
    DECO_LINE_ASPECT_RATIO = 15.0
    DECO_LINE_PAGE_SPAN = 0.5
    MERGE_OVERLAP_PAD = 2
    MIN_LTIMAGE_SIZE = 5
    MIN_NON_IMAGE_SIZE = 2

    def __init__(self, debug_curves: bool = False):
        self.debug_curves = debug_curves

    def merge_path_bboxes(self, bboxes: List, page_w: int, page_h: int,
                          cell_size=None, num_rows: int = 0) -> List:
        if not bboxes:
            return []
        if len(bboxes) == 1 or self.debug_curves:
            return bboxes
        return self._morphological_merge(bboxes, page_w, page_h)

    def _morphological_merge(self, bboxes, page_w, page_h):
        scale = self.MORPH_SCALE
        radius = self.MORPH_DILATE_RADIUS
        min_area = self.MORPH_MIN_AREA
        deco_span = self.DECO_LINE_PAGE_SPAN
        bw = page_w * scale
        bh = page_h * scale
        canvas = np.zeros((bh, bw), dtype=np.uint8)
        for x0, y0, x1, y1 in bboxes:
            w = x1 - x0
            h = y1 - y0
            if w > page_w * deco_span or h > page_h * deco_span:
                continue
            x0_c = max(0, int(x0 * scale))
            y0_c = max(0, int(y0 * scale))
            x1_c = min(bw, int(x1 * scale) + 1)
            y1_c = min(bh, int(y1 * scale) + 1)
            if x0_c < x1_c and y0_c < y1_c:
                canvas[y0_c:y1_c, x0_c:x1_c] = 255
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (radius * scale * 2 + 1, radius * scale * 2 + 1))
        canvas = cv2.morphologyEx(canvas, cv2.MORPH_CLOSE, kernel)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(canvas)
        result = []
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < min_area:
                continue
            x = stats[i, cv2.CC_STAT_LEFT] / scale
            y = stats[i, cv2.CC_STAT_TOP] / scale
            w = stats[i, cv2.CC_STAT_WIDTH] / scale
            h = stats[i, cv2.CC_STAT_HEIGHT] / scale
            result.append((x, y, x + w, y + h))
        return result

    # ------------------------------------------------------------------
    #  image / figure processing
    # ------------------------------------------------------------------

    def merge_overlapping_images(self, elements: List) -> List:
        if len(elements) < 2 or self.debug_curves:
            return elements
        while True:
            n = len(elements)
            groups = self._find_overlap_groups(elements)
            if groups is None:
                break
            new_elements = self._combine_overlap_groups(groups)
            if len(new_elements) >= n:
                break
            elements = new_elements
        return elements

    @staticmethod
    def _pad_bbox(elem):
        pad = VisualExtractor.MERGE_OVERLAP_PAD
        if isinstance(elem, _MergedElement):
            return elem.bbox[:]
        if isinstance(elem, (LTImage, LTFigure)):
            return elem.bbox[:]
        b = elem.bbox
        return [b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad]

    def _find_overlap_groups(self, elements):
        n = len(elements)
        parent = list(range(n))

        def _find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def _union(i, j):
            ri, rj = _find(i), _find(j)
            if ri != rj:
                parent[ri] = rj

        merged_count = 0
        for i in range(n):
            bi = self._pad_bbox(elements[i])
            for j in range(i + 1, n):
                bj = self._pad_bbox(elements[j])
                if (bi[0] < bj[2] and bi[2] > bj[0]
                        and bi[1] < bj[3] and bi[3] > bj[1]):
                    if _find(i) != _find(j):
                        _union(i, j)
                        merged_count += 1
        if merged_count == 0:
            return None
        groups = {}
        for i in range(n):
            root = _find(i)
            groups.setdefault(root, []).append(elements[i])
        return groups

    @staticmethod
    def _combine_overlap_groups(groups):
        new_elements = []
        for group in groups.values():
            if len(group) == 1:
                new_elements.append(group[0])
            else:
                x0 = min(im.bbox[0] for im in group)
                y0 = min(im.bbox[1] for im in group)
                x1 = max(im.bbox[2] for im in group)
                y1 = max(im.bbox[3] for im in group)
                name = getattr(group[0], "name", None)
                new_elements.append(_MergedElement((x0, y0, x1, y1), name))
        return new_elements

    def extract_from_figure(self, figure: LTFigure) -> List:
        children = []
        self._collect_figure_children(figure, children)
        images = [c for c in children if isinstance(c, LTImage)]
        sub_figures = [c for c in children
                       if isinstance(c, LTFigure) and c is not figure]
        curves = [c for c in children
                  if isinstance(c, LTCurve) and not isinstance(c, LTFigure)]
        if not images and not sub_figures:
            return [figure]
        result = []
        if curves:
            if self.debug_curves:
                for c in curves:
                    result.append(_MergedElement(c.bbox, name=getattr(figure, 'name', None)))
            else:
                merged = self._merge_bboxes(curves, name=getattr(figure, 'name', None))
                if merged:
                    result.append(merged)
        result.extend(images)
        result.extend(sub_figures)
        return result if result else []

    @staticmethod
    def _collect_figure_children(figure, elements_list: List):
        elements_list.append(figure)
        if hasattr(figure, '_objs'):
            for child in figure._objs:
                VisualExtractor._collect_figure_children(child, elements_list)

    @staticmethod
    def _merge_bboxes(elements, name=None):
        if not elements:
            return None
        x0 = min(e.bbox[0] for e in elements)
        y0 = min(e.bbox[1] for e in elements)
        x1 = max(e.bbox[2] for e in elements)
        y1 = max(e.bbox[3] for e in elements)
        return _MergedElement((x0, y0, x1, y1), name)

    # ------------------------------------------------------------------
    #  image info extraction
    # ------------------------------------------------------------------

    def process_image(self, image, page_height: float,
                      page_w: int = None, page_h: int = None) -> Dict:
        try:
            x_tl, x_br, w, y_tl, y_br, h = coord.get_coords(
                image.bbox, page_height)
            if page_w is not None and page_h is not None:
                x_tl, y_tl = max(0, x_tl), max(0, y_tl)
                x_br, y_br = min(page_w, x_br), min(page_h, y_br)
                w, h = x_br - x_tl, y_br - y_tl
            w, h = self._enforce_min_size(image, w, h)
            if w <= 0 or h <= 0:
                return None
            if self._ltimage_too_small(image, w, h):
                return None
            info = {
                "segment": {
                    "x_top_left": math.ceil(x_tl),
                    "y_top_left": math.ceil(y_tl),
                    "width": math.ceil(w),
                    "height": math.ceil(h),
                },
                "text": " ",
            }
            if hasattr(image, 'name'):
                info['image_name'] = getattr(image, 'name', '')
            return info
        except Exception:
            return None

    def _enforce_min_size(self, image, w, h):
        if not isinstance(image, LTImage):
            w = max(w, self.MIN_NON_IMAGE_SIZE)
            h = max(h, self.MIN_NON_IMAGE_SIZE)
        return w, h

    def _ltimage_too_small(self, image, w, h):
        return (isinstance(image, LTImage)
                and (w < self.MIN_LTIMAGE_SIZE or h < self.MIN_LTIMAGE_SIZE))

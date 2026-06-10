import math
from typing import Dict, List

from pdfminer.layout import LTImage, LTFigure, LTCurve

from . import coordinate_utils as coord
from .merged_element import _MergedElement, _PreMergedBox
from .text_extractor import TextExtractor


class VisualExtractor:
    GRID_CELL_SIZE = 8
    GRID_MAX_CELLS = 2_000_000
    DECO_LINE_ASPECT_RATIO = 15.0
    DECO_LINE_PAGE_SPAN = 0.5
    MERGE_OVERLAP_PAD = 2
    MIN_LTIMAGE_SIZE = 5
    MIN_NON_IMAGE_SIZE = 2

    def __init__(self, debug_curves: bool = False):
        self.debug_curves = debug_curves

    # ------------------------------------------------------------------
    #  path bbox merging  (occupancy grid + BFS)
    # ------------------------------------------------------------------

    def merge_path_bboxes(self, bboxes: List, page_w: int, page_h: int,
                          cell_size: int = None) -> List:
        if cell_size is None:
            cell_size = self.GRID_CELL_SIZE
        if not bboxes:
            return []
        if len(bboxes) == 1 or self.debug_curves:
            return bboxes
        gw, gh, cell_size = self._grid_dimensions(page_w, page_h, cell_size)
        grid = self._fill_grid(bboxes, gw, gh, cell_size, page_w, page_h)
        return self._flood_grid_components(grid, gw, gh, cell_size)

    @staticmethod
    def _grid_dimensions(page_w, page_h, cell_size):
        gw = max(1, page_w // cell_size + 1)
        gh = max(1, page_h // cell_size + 1)
        total = gw * gh
        if total > VisualExtractor.GRID_MAX_CELLS:
            cell_size = max(1, int((page_w * page_h) ** 0.5 / 1400))
            gw = max(1, page_w // cell_size + 1)
            gh = max(1, page_h // cell_size + 1)
        return gw, gh, cell_size

    @staticmethod
    def _fill_grid(bboxes, gw, gh, cell_size, page_w, page_h):
        grid = bytearray(gw * gh)
        dilate = max(1, cell_size // 4)
        deco_ratio = VisualExtractor.DECO_LINE_ASPECT_RATIO
        deco_span = VisualExtractor.DECO_LINE_PAGE_SPAN
        for x0, y0, x1, y1 in bboxes:
            w = x1 - x0
            h = y1 - y0
            if w < 2 and h < 2:
                continue
            if w > page_w * deco_span and w / max(h, 1) > deco_ratio:
                continue
            if h > page_h * deco_span and h / max(w, 1) > deco_ratio:
                continue
            gx0 = max(0, int((x0 - dilate) / cell_size))
            gy0 = max(0, int((y0 - dilate) / cell_size))
            gx1 = min(gw - 1, int((x1 + dilate) / cell_size))
            gy1 = min(gh - 1, int((y1 + dilate) / cell_size))
            if gx0 > gx1 or gy0 > gy1:
                continue
            for gy in range(gy0, gy1 + 1):
                row_off = gy * gw
                for gx in range(gx0, gx1 + 1):
                    grid[row_off + gx] = 1
        return grid

    @staticmethod
    def _flood_grid_components(grid, gw, gh, cell_size):
        components = []
        stack = []
        for start_gy in range(gh):
            row_off = start_gy * gw
            for start_gx in range(gw):
                if grid[row_off + start_gx] == 0:
                    continue
                min_cx = max_cx = start_gx
                min_cy = max_cy = start_gy
                stack.append((start_gx, start_gy))
                grid[row_off + start_gx] = 0
                while stack:
                    cx, cy = stack.pop()
                    if cx < min_cx:
                        min_cx = cx
                    elif cx > max_cx:
                        max_cx = cx
                    if cy < min_cy:
                        min_cy = cy
                    elif cy > max_cy:
                        max_cy = cy
                    for dx in (-1, 0, 1):
                        nx = cx + dx
                        if nx < 0 or nx >= gw:
                            continue
                        for dy in (-1, 0, 1):
                            if dx == 0 and dy == 0:
                                continue
                            ny = cy + dy
                            if ny < 0 or ny >= gh:
                                continue
                            if grid[ny * gw + nx]:
                                grid[ny * gw + nx] = 0
                                stack.append((nx, ny))
                components.append((
                    min_cx * cell_size,
                    min_cy * cell_size,
                    (max_cx + 1) * cell_size,
                    (max_cy + 1) * cell_size,
                ))
        return components

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

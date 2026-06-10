from pdfminer.converter import PDFPageAggregator
from pdfminer.utils import apply_matrix_pt


class _FastPDFPageAggregator(PDFPageAggregator):
    """Aggregator that records path bboxes for fast merging *and* creates
    minimal layout objects so that figure/curve grouping is preserved.

    Paths are recorded by their bounding box only. Tracks figure nesting
    so that paths belonging to the same Form XObject are grouped together.
    """
    def __init__(self, rsrcmgr, laparams=None):
        super().__init__(rsrcmgr, laparams=laparams)
        self._path_bboxes = []
        self._figure_bboxes = {}
        self._figure_stack = []
        self._fid_counter = 0

    def begin_figure(self, name, bbox, matrix):
        super().begin_figure(name, bbox, matrix)
        fid = self._fid_counter
        self._fid_counter += 1
        self._figure_stack.append(fid)
        self._figure_bboxes[fid] = []

    def end_figure(self, name):
        super().end_figure(name)
        if self._figure_stack:
            self._figure_stack.pop()

    def paint_path(self, gstate, stroke, fill, evenodd, path):
        if not path:
            return
        linew = gstate.linewidth if gstate.linewidth else 1.0
        pad = max(1.0, linew * 0.5)
        ctm = self.ctm
        seg0 = path[0]
        pts = seg0[1:]
        x0, y0 = apply_matrix_pt(ctm, (pts[0], pts[1]))
        min_x = max_x = x0
        min_y = max_y = y0
        for k in range(2, len(pts), 2):
            x, y = apply_matrix_pt(ctm, (pts[k], pts[k + 1]))
            if x < min_x: min_x = x
            elif x > max_x: max_x = x
            if y < min_y: min_y = y
            elif y > max_y: max_y = y
        for seg in path[1:]:
            pts = seg[1:]
            for k in range(0, len(pts), 2):
                x, y = apply_matrix_pt(ctm, (pts[k], pts[k + 1]))
                if x < min_x: min_x = x
                elif x > max_x: max_x = x
                if y < min_y: min_y = y
                elif y > max_y: max_y = y
        if min_x < max_x and min_y < max_y:
            bbox = (min_x - pad, min_y - pad, max_x + pad, max_y + pad)
            if self._figure_stack:
                self._figure_bboxes[self._figure_stack[-1]].append(bbox)
            else:
                self._path_bboxes.append(bbox)

    def get_path_bboxes(self):
        return self._path_bboxes

    def get_figure_path_bboxes(self):
        return self._figure_bboxes

    def clear_path_bboxes(self):
        self._path_bboxes = []
        self._figure_bboxes = {}
        self._figure_stack = []
        self._fid_counter = 0

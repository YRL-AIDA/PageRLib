import math
from typing import Dict, List

from pdfminer.layout import LTChar, LTTextLine

from . import coordinate_utils as coord
from . import char_lines


class TextExtractor:
    MAX_TEXT_LINE_HEIGHT = 50
    VERTICAL_X_GAP = 3
    VERTICAL_MIN_RUN = 3
    VERTICAL_GAP_MULT = 4
    VERTICAL_GAP_MIN = 6
    VERTICAL_GAP_HEIGHT_FACTOR = 0.5
    VERTICAL_GAP_HEIGHT_MAX = 1.5

    def process_text_line(self, text_line: LTTextLine, page_height: float) -> Dict:
        if not text_line.get_text().strip():
            return None
        x0, y0, x1, y1 = text_line.x0, text_line.y0, text_line.x1, text_line.y1
        x_tl, x_br, w, y_tl, y_br, h = coord.get_coords(
            [x0, y0, x1, y1], page_height)
        if h > self.MAX_TEXT_LINE_HEIGHT:
            return None
        words = self._extract_words(text_line, page_height)
        return {
            "segment": {
                "x_top_left": math.ceil(x_tl),
                "y_top_left": math.ceil(y_tl),
                "width": math.ceil(w),
                "height": math.ceil(h),
            },
            "text": text_line.get_text().strip(),
            "words": words,
        }

    def _extract_words(self, text_line: LTTextLine, page_height: float) -> List[Dict]:
        words = []
        cur_chars = []
        cur_bbox = None
        font_info = {}
        for child in text_line:
            if isinstance(child, LTChar):
                ct = child.get_text()
                cb = child.bbox
                if ct.strip() and not ct.isspace():
                    if not cur_chars:
                        cur_bbox = list(cb)
                        font_info = {
                            "fontname": child.fontname,
                            "fontsize": child.size,
                            "is_normal": child.upright,
                        }
                    else:
                        cur_bbox[0] = min(cur_bbox[0], cb[0])
                        cur_bbox[1] = min(cur_bbox[1], cb[1])
                        cur_bbox[2] = max(cur_bbox[2], cb[2])
                        cur_bbox[3] = max(cur_bbox[3], cb[3])
                    cur_chars.append(ct)
                else:
                    if cur_chars:
                        words.append(self._create_word(
                            cur_chars, cur_bbox, page_height, font_info))
                        cur_chars = []
                        font_info = {}
                        cur_bbox = None
        if cur_chars:
            words.append(self._create_word(
                cur_chars, cur_bbox, page_height, font_info))
        return [w for w in words if self.is_correct_segment(w['segment'])]

    def _create_word(self, chars: List[str], bbox: List[float],
                     page_height: float, font_info: Dict) -> Dict:
        text = ''.join(chars)
        x_tl, x_br, w, y_tl, y_br, h = coord.get_coords(bbox, page_height)
        return {
            "segment": {
                "x_top_left": math.ceil(x_tl),
                "y_top_left": math.ceil(y_tl),
                "width": math.ceil(w),
                "height": math.ceil(h),
            },
            "text": text,
            "font": font_info,
        }

    @staticmethod
    def is_correct_segment(segment):
        return segment['width'] > 0 and segment['height'] > 0

    # ------------------------------------------------------------------
    #  vertical row merging
    # ------------------------------------------------------------------

    def merge_vertical_rows(self, rows: List[Dict]) -> List[Dict]:
        if not rows:
            return rows
        candidates = self._find_vertical_candidates(rows)
        if len(candidates) < 2:
            return rows
        x_groups = self._group_by_x_position(candidates)
        all_runs = []
        for group in x_groups.values():
            if len(group) < 2:
                continue
            gap_result = self._calc_vertical_gap(group)
            if gap_result is None:
                continue
            max_gap = gap_result
            runs = self._build_vertical_runs(group, max_gap)
            all_runs.extend(runs)
        merged_data, used = self._merge_runs_to_rows(all_runs)
        result = [r for r in rows if id(r) not in used]
        result.extend(merged_data)
        return result

    @staticmethod
    def _find_vertical_candidates(rows: List[Dict]) -> List[Dict]:
        candidates = []
        for r in rows:
            text = r.get("text", "")
            words = r.get("words", [])
            if len(text) == 1 and len(words) == 1:
                candidates.append(r)
        return candidates

    @staticmethod
    def _group_by_x_position(candidates: List[Dict]) -> Dict:
        cfg = TextExtractor
        x_groups = {}
        for r in candidates:
            xc = round(r["segment"]["x_top_left"], 0)
            found = False
            for key in list(x_groups.keys()):
                if abs(key - xc) <= cfg.VERTICAL_X_GAP:
                    x_groups[key].append(r)
                    found = True
                    break
            if not found:
                x_groups[xc] = [r]
        return x_groups

    def _calc_vertical_gap(self, group: List[Dict]):
        group.sort(key=lambda r: r["segment"]["y_top_left"])
        heights = sorted([r["segment"]["height"] for r in group])
        char_h = heights[len(heights) // 2]
        y_gaps = []
        for i in range(1, len(group)):
            prev_bot = (group[i - 1]["segment"]["y_top_left"] +
                        group[i - 1]["segment"]["height"])
            curr_top = group[i]["segment"]["y_top_left"]
            y_gaps.append(curr_top - prev_bot)
        if not y_gaps:
            return None
        y_gaps.sort()
        med_gap = y_gaps[len(y_gaps) // 2]
        max_gap = min(
            max(med_gap * self.VERTICAL_GAP_MULT,
                char_h * self.VERTICAL_GAP_HEIGHT_FACTOR,
                self.VERTICAL_GAP_MIN),
            char_h * self.VERTICAL_GAP_HEIGHT_MAX)
        return max_gap

    @staticmethod
    def _build_vertical_runs(group: List[Dict], max_gap) -> List[List[Dict]]:
        cfg = TextExtractor
        group.sort(key=lambda r: r["segment"]["y_top_left"])
        run = [group[0]]
        runs = []
        for i in range(1, len(group)):
            prev_bot = (group[i - 1]["segment"]["y_top_left"] +
                        group[i - 1]["segment"]["height"])
            curr_top = group[i]["segment"]["y_top_left"]
            gap = curr_top - prev_bot
            if gap <= max_gap:
                run.append(group[i])
            else:
                if len(run) >= cfg.VERTICAL_MIN_RUN:
                    runs.append(run)
                run = [group[i]]
        if len(run) >= cfg.VERTICAL_MIN_RUN:
            runs.append(run)
        return runs

    @staticmethod
    def _merge_runs_to_rows(merged_runs: List[List[Dict]]):
        merged_rows = []
        used = set()
        for run in merged_runs:
            for r in run:
                used.add(id(r))
            run.sort(key=lambda r: r["segment"]["y_top_left"])
            texts = [r["text"] for r in run]
            all_words = []
            for r in run:
                all_words.extend(r["words"])
            x0 = min(r["segment"]["x_top_left"] for r in run)
            y0 = min(r["segment"]["y_top_left"] for r in run)
            x1 = max(r["segment"]["x_top_left"] + r["segment"]["width"]
                     for r in run)
            y1 = max(r["segment"]["y_top_left"] + r["segment"]["height"]
                     for r in run)
            merged_rows.append({
                "segment": {
                    "x_top_left": x0, "y_top_left": y0,
                    "width": x1 - x0, "height": y1 - y0,
                },
                "text": "".join(texts),
                "words": all_words,
            })
        return merged_rows, used

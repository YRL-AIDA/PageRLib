from typing import List

from pdfminer.layout import LTChar


VERTICAL_CHAR_RATIO = 1.5
CHAR_LINE_ALIGN = 2
CHAR_SPLIT_GAP_MULT = 3
CHAR_SPLIT_MIN_GAP = 15


def _chars_to_text_line(chars):
    class _Line:
        def __init__(self, chs):
            self._chars = chs
            xs, ys = [], []
            for c in chs:
                xs.extend([c.bbox[0], c.bbox[2]])
                ys.extend([c.bbox[1], c.bbox[3]])
            self.x0 = min(xs) if xs else 0
            self.y0 = min(ys) if ys else 0
            self.x1 = max(xs) if xs else 0
            self.y1 = max(ys) if ys else 0

        def get_text(self):
            return "".join(c.get_text() for c in self._chars)

        def __iter__(self):
            return iter(self._chars)

    return _Line(chars)


def is_vertical_char(c: LTChar) -> bool:
    h = c.y1 - c.y0
    w = c.x1 - c.x0
    return (h > w * VERTICAL_CHAR_RATIO
            and w > 0 and not getattr(c, "upright", True))


def chars_to_text_lines(chars: List) -> List:
    if not chars:
        return []
    horizontal = [c for c in chars if not is_vertical_char(c)]
    vertical = [c for c in chars if is_vertical_char(c)]
    lines = []
    if horizontal:
        lines.extend(_group_chars_by_axis(horizontal, axis="y"))
    if vertical:
        lines.extend(_group_chars_by_axis(vertical, axis="x"))
    return lines


def _group_chars_by_axis(chars: List, axis: str):
    cfg = CHAR_LINE_ALIGN
    key = (lambda c: (c.y0, c.x0)) if axis == "y" else (
        lambda c: (c.x0, c.y0))
    sorted_chars = sorted(chars, key=key)
    result = []
    current = [sorted_chars[0]]
    for c in sorted_chars[1:]:
        prev = current[-1]
        if axis == "y":
            same = abs(c.y0 - prev.y0) <= cfg and abs(c.y1 - prev.y1) <= cfg
        else:
            same = abs(c.x0 - prev.x0) <= cfg and abs(c.x1 - prev.x1) <= cfg
        if same:
            current.append(c)
        else:
            _split_and_add_lines(current, result, axis)
            current = [c]
    if current:
        _split_and_add_lines(current, result, axis)
    return result


def _split_and_add_lines(chars: List, output: List, axis: str = "x"):
    if len(chars) <= 1:
        output.append(_chars_to_text_line(chars))
        return
    if axis == "y":
        s = sorted(chars, key=lambda ch: ch.x0)
    else:
        s = sorted(chars, key=lambda ch: ch.y1)
    gaps = []
    for i in range(1, len(s)):
        if axis == "y":
            gaps.append(s[i].x0 - s[i - 1].x1)
        else:
            gaps.append(s[i].y0 - s[i - 1].y1)
    gaps.sort()
    med = gaps[len(gaps) // 2]
    thr = max(med * CHAR_SPLIT_GAP_MULT, CHAR_SPLIT_MIN_GAP)
    segment = [s[0]]
    for i in range(1, len(s)):
        if axis == "y":
            gap = s[i].x0 - s[i - 1].x1
        else:
            gap = s[i].y0 - s[i - 1].y1
        if gap > thr:
            output.append(_chars_to_text_line(segment))
            segment = [s[i]]
        else:
            segment.append(s[i])
    if segment:
        output.append(_chars_to_text_line(segment))

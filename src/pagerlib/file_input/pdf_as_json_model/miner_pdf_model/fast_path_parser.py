"""Fast content-stream parser that extracts path bounding boxes from raw bytes.

Parses PDF content streams with a lightweight byte scanner (no regex),
tracking the CTM to produce device-coordinate bboxes for every painted path.
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# --- byte classification constants -------------------------------------------------
_WS = frozenset((0, 9, 10, 12, 13, 32))
_DELIM = frozenset((40, 41, 60, 62, 91, 93, 123, 125, 47, 37))
_ORD_PCT = 37     # '%'  comment
_ORD_SLASH = 47   # '/'  name
_ORD_LPAREN = 40   # '('  string
_ORD_RPAREN = 41   # ')'  string end
_ORD_LANGLE = 60   # '<'  hex / dict
_ORD_RANGLE = 62   # '>'  hex / dict end
_ORD_LBRACKET = 91 # '['  array
_ORD_RBRACKET = 93 # ']'  array end
_ORD_CR = 13
_ORD_LF = 10
_ORD_BSLASH = 92  # '\\' escape

# --- operator ordinals --------------------------------------------------------------
_O_Q = 113   # 'q' save graphics state
_O_QQ = 81   # 'Q' restore
_O_m = 109   # 'm' moveto
_O_l = 108   # 'l' lineto
_O_c = 99    # 'c' curveto
_O_v = 118   # 'v' curveto
_O_y = 121   # 'y' curveto
_O_h = 104   # 'h' closepath
_OP_cm = b'cm'
_OP_re = b're'
_PAINT_1 = frozenset((83, 102, 70, 66, 98, 110, 115))  # S f F B b n s
_FLUSH_2 = frozenset((b'B*', b'b*', b'f*', b'W*'))
_O_W = 87    # 'W' clip

# --- CTM helpers --------------------------------------------------------------------
_ID_CTM = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _concat_ctm(ctm, a, b, c, d, e, f):
    oa, ob, oc, od, oe, of_ = ctm
    return (
        a * oa + b * oc,
        a * ob + b * od,
        c * oa + d * oc,
        c * ob + d * od,
        e * oa + f * oc + oe,
        e * ob + f * od + of_,
    )


def _apply_ctm(ctm, x, y):
    a, b, c, d, e, f = ctm
    return a * x + c * y + e, b * x + d * y + f


# --- token scanner ------------------------------------------------------------------
def _is_regular(byte: int) -> bool:
    return byte not in _WS and byte not in _DELIM


def _skip_comment(data, pos, length):
    pos += 1
    while pos < length and data[pos] not in (_ORD_CR, _ORD_LF):
        pos += 1
    return pos


def _skip_string(data, pos, length):
    depth = 1
    pos += 1
    while pos < length and depth > 0:
        ch = data[pos]
        if ch == _ORD_LPAREN:
            depth += 1
        elif ch == _ORD_RPAREN:
            depth -= 1
        elif ch == _ORD_BSLASH:
            pos += 1
        pos += 1
    return pos


def _skip_hex_or_dict(data, pos, length):
    if pos + 1 < length and data[pos + 1] == _ORD_LANGLE:
        pos += 2
        while pos < length - 1:
            if data[pos] == _ORD_RANGLE and data[pos + 1] == _ORD_RANGLE:
                return pos + 2
            pos += 1
        return pos
    pos += 1
    while pos < length and data[pos] != _ORD_RANGLE:
        pos += 1
    return pos + 1 if pos < length else pos


def _skip_array(data, pos, length):
    depth = 1
    pos += 1
    while pos < length and depth > 0:
        ch = data[pos]
        if ch == _ORD_LBRACKET:
            depth += 1
        elif ch == _ORD_RBRACKET:
            depth -= 1
        pos += 1
    return pos


# --- token stream generator ---------------------------------------------------------
def _iter_tokens(data: memoryview):
    """Yield (bytes_token | float, is_op) tuples from a content stream."""
    length = len(data)
    pos = 0
    while pos < length:
        byte = data[pos]
        if byte in _WS:
            pos += 1
            continue
        if byte == _ORD_PCT:
            pos = _skip_comment(data, pos, length)
            continue
        if byte == _ORD_SLASH:
            pos += 1
            while pos < length and _is_regular(data[pos]):
                pos += 1
            continue  # skip names
        if byte == _ORD_LPAREN:
            pos = _skip_string(data, pos, length)
            continue
        if byte == _ORD_LANGLE:
            pos = _skip_hex_or_dict(data, pos, length)
            continue
        if byte == _ORD_LBRACKET:
            pos = _skip_array(data, pos, length)
            continue
        if _is_regular(byte):
            start = pos
            pos += 1
            while pos < length and _is_regular(data[pos]):
                pos += 1
            token = bytes(data[start:pos])
            is_num = True
            has_digit = False
            for ch in token:
                if 48 <= ch <= 57:  # '0'-'9'
                    has_digit = True
                elif ch in (43, 45, 46):  # '+' '-' '.'
                    pass
                else:
                    is_num = False
                    break
            if is_num and has_digit:
                yield float(token)
            else:
                yield token
        else:
            pos += 1


# --- bbox extraction from token stream ----------------------------------------------
_PATH_PAD = 0.5


def _extract_bboxes(tokens) -> List[Tuple[float, ...]]:
    result: List[Tuple[float, ...]] = []
    ctm_stack = [_ID_CTM]
    ctm = ctm_stack[-1]
    pmin_x = pmin_y = pmax_x = pmax_y = None
    stack = []

    def _flush():
        nonlocal pmin_x, pmin_y, pmax_x, pmax_y
        if pmin_x is not None:
            if pmin_x >= pmax_x:
                pmin_x -= _PATH_PAD
                pmax_x += _PATH_PAD
            if pmin_y >= pmax_y:
                pmin_y -= _PATH_PAD
                pmax_y += _PATH_PAD
            if pmin_x < pmax_x and pmin_y < pmax_y:
                result.append((pmin_x, pmin_y, pmax_x, pmax_y))
        pmin_x = pmin_y = pmax_x = pmax_y = None

    def _add(px, py):
        nonlocal pmin_x, pmin_y, pmax_x, pmax_y
        if pmin_x is None:
            pmin_x = pmax_x = px
            pmin_y = pmax_y = py
        else:
            if px < pmin_x: pmin_x = px
            elif px > pmax_x: pmax_x = px
            if py < pmin_y: pmin_y = py
            elif py > pmax_y: pmax_y = py

    for token in tokens:
        if isinstance(token, float):
            stack.append(token)
            continue

        op = token
        if op == b'cm' and len(stack) >= 6:
            f = stack.pop(); e = stack.pop(); d = stack.pop()
            cv = stack.pop(); b = stack.pop(); a = stack.pop()
            ctm = _concat_ctm(ctm, a, b, cv, d, e, f)
            ctm_stack[-1] = ctm

        elif op == b're' and len(stack) >= 4:
            h = stack.pop(); w = stack.pop()
            y = stack.pop(); x = stack.pop()
            _flush()
            for px_u, py_u in ((x, y), (x + w, y), (x + w, y + h), (x, y + h)):
                _add(*_apply_ctm(ctm, px_u, py_u))
            _flush()

        elif len(op) == 1:
            o = op[0]
            if o == _O_Q:
                ctm_stack.append(ctm)
            elif o == _O_QQ:
                if len(ctm_stack) > 1:
                    ctm_stack.pop()
                ctm = ctm_stack[-1]
            elif o == _O_m and len(stack) >= 2:
                y = stack.pop(); x = stack.pop()
                _flush()
                _add(*_apply_ctm(ctm, x, y))
            elif o == _O_l and len(stack) >= 2:
                y = stack.pop(); x = stack.pop()
                _add(*_apply_ctm(ctm, x, y))
            elif o == _O_c and len(stack) >= 6:
                stack.pop(); stack.pop(); stack.pop(); stack.pop()
                y3 = stack.pop(); x3 = stack.pop()
                _add(*_apply_ctm(ctm, x3, y3))
            elif o == _O_v and len(stack) >= 4:
                stack.pop(); stack.pop()
                y3 = stack.pop(); x3 = stack.pop()
                _add(*_apply_ctm(ctm, x3, y3))
            elif o == _O_y and len(stack) >= 4:
                stack.pop(); stack.pop()
                y3 = stack.pop(); x3 = stack.pop()
                _add(*_apply_ctm(ctm, x3, y3))
            elif o in _PAINT_1 or o == _O_W or o == _O_h:
                _flush()
        elif op in _FLUSH_2:
            _flush()

    _flush()
    return result


# --- public API ---------------------------------------------------------------------
def extract_path_bboxes_from_bytes(content_bytes: bytes) -> List[Tuple[float, ...]]:
    """Parse *content_bytes* and return list of (x0, y0, x1, y1) bboxes."""
    if not content_bytes:
        return []
    data = memoryview(content_bytes)
    return _extract_bboxes(_iter_tokens(data))

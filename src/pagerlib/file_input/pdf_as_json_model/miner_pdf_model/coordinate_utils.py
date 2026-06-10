def pdf_to_pixel(x, y, page_height_points, dpi=None):
    if dpi is None:
        dpi = 72
    x_px = x * dpi / 72.0
    y_px = (page_height_points - y) * dpi / 72.0
    return int(x_px), int(y_px)


def get_coords(bbox, page_height):
    x_ll, y_ll, x_ur, y_ur = bbox
    x0, y0 = pdf_to_pixel(x_ll, y_ur, page_height)
    x1, y1 = pdf_to_pixel(x_ur, y_ll, page_height)
    x_tl = min(x0, x1)
    x_br = max(x0, x1)
    y_tl = min(y0, y1)
    y_br = max(y0, y1)
    w = x_br - x_tl
    h = y_br - y_tl
    return x_tl, x_br, w, y_tl, y_br, h

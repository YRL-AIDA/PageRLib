"""OCR engine: extracts words from a numpy image array via Tesseract.

Returns a row-structured word list with bounding boxes and confidence scores.
"""

import pytesseract

import cv2
import numpy as np
from pagerlib.dtypes import Image, Region


class Image2Words:
    def __init__(self, conf=None):
        self.conf = {"lang": "eng+rus", "psm": 4, "oem": 3, "k": 1, "onetone_delete": False}
        if conf is None:
            return
        for key, val in conf.items():
            if key in self.conf.keys():
                self.conf[key] = val

    def get_region(self, image: Image) -> Region:
        row_list = self.extract_from_img(image.img)
        rows = []
        others = []
        for r in row_list:
            if len(r['words']) == 0:
                others.append(r)
            else:
                rows.append(r)
        if len(rows) == 0:
            return Region.get_none()
        return Region(children=rows)

    def extract_from_img(self, img):
        conf = self.conf
        dim = (conf["k"] * img.shape[1], conf["k"] * img.shape[0])
        img_ = cv2.resize(img, dim, interpolation=cv2.INTER_AREA)
        tesseract_bboxes = pytesseract.image_to_data(
            config=f"-l {conf['lang']} --psm {conf['psm']} --oem {conf['oem']}",
            image=img_,
            output_type=pytesseract.Output.DICT)
        row_list = []
        st = -1
        word_idx = 0
        for level, left, top, width, height, text in zip(tesseract_bboxes["level"],
                                                          tesseract_bboxes["left"],
                                                          tesseract_bboxes["top"],
                                                          tesseract_bboxes["width"],
                                                          tesseract_bboxes["height"],
                                                          tesseract_bboxes["text"]):
            if level == 4:
                st += 1
                x0 = round(left / conf["k"])
                y0 = round(top / conf["k"])
                w = round(width / conf["k"])
                h = round(height / conf["k"])
                # TODO: сделать фильтр ширины, поменять однотонный фильтер
                if conf["onetone_delete"] and np.var(img[y0:y0 + h, x0:x0 + w]) < 20:
                    continue
                row_list.append({
                    "words": [],
                    "segment": {
                        "x_top_left": x0,
                        "y_top_left": y0,
                        "width": w,
                        "height": h
                    }
                })

            if level == 5:
                x0 = round(left / conf["k"])
                y0 = round(top / conf["k"])
                w = round(width / conf["k"])
                h = round(height / conf["k"])
                conf_val = tesseract_bboxes["conf"][word_idx]
                word_idx += 1
                row_list[st]['words'].append({
                    "text": text,
                    "conf": float(conf_val),
                    "segment": {
                        "x_top_left": x0,
                        "y_top_left": y0,
                        "width": w,
                        "height": h
                    }}
                )

        row_list = self.word_clip_filter(row_list)
        row_list = self.size_filter(row_list)
        return row_list

    def word_clip_filter(self, row_list):
        for row in row_list:
            row_left = row["segment"]["x_top_left"]
            row_top = row["segment"]["y_top_left"]
            row_right = row_left + row["segment"]["width"]
            row_bottom = row_top + row["segment"]["height"]
            for word in row["words"]:
                seg = word["segment"]
                word_left = seg["x_top_left"]
                word_top = seg["y_top_left"]
                word_right = word_left + seg["width"]
                word_bottom = word_top + seg["height"]

                # Compute intersection with row
                left = max(word_left, row_left)
                top = max(word_top, row_top)
                right = min(word_right, row_right)
                bottom = min(word_bottom, row_bottom)

                seg["x_top_left"] = left
                seg["y_top_left"] = top
                seg["width"] = max(1, right - left)
                seg["height"] = max(1, bottom - top)
                
        return row_list

    def size_filter(self, row_list):
        return [row for row in row_list if row['segment']["width"] >= 2 and row['segment']["height"] >= 2]


import re
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

    def get_region(self, image:Image)-> None:
        row_list = self.extract_from_img(image.img)
        rows = []
        others = []
        for r in row_list:
            if len(r['words'])==0:
                print(r)
                others.append(r)
            else:
                rows.append(r)
        return Region(children=rows)


    def extract_from_img(self, img):
        conf = self.conf
        dim = (conf["k"]*img.shape[1], conf["k"]*img.shape[0])
        img_ = cv2.resize(img, dim, interpolation = cv2.INTER_AREA)
        tesseract_bboxes = pytesseract.image_to_data(
            config=f"-l {conf['lang']} --psm {conf['psm']} --oem {conf['oem']}",
            image=img_,
            output_type=pytesseract.Output.DICT)
        row_list = []
        st = -1
        for level, left, top, width, height, text in zip(tesseract_bboxes["level"],
                                                   tesseract_bboxes["left"],
                                                   tesseract_bboxes["top"],
                                                   tesseract_bboxes["width"],
                                                   tesseract_bboxes["height"],
                                                   tesseract_bboxes["text"]):
            if level == 4:
                st += 1
                x0 = round(left/conf["k"])
                y0 = round(top/conf["k"])
                w = round(width/conf["k"])
                h = round(height/conf["k"])
                # TODO: сделать фильтр ширины, поменять однотонный фильтер
                if conf["onetone_delete"] and np.var(img[y0:y0+h, x0:x0+w]) < 20:
                    continue
                row_list.append({
                    "words": [],
                    "segment":{
                        "x_top_left": x0,
                        "y_top_left": y0,
                        "width": w,
                        "height": h
                    }
                })
                
            if level == 5:
                x0 = round(left/conf["k"])
                y0 = round(top/conf["k"])
                w = round(width/conf["k"])
                h = round(height/conf["k"])
                row_list[st]['words'].append({
                    "text": text,
                    "segment":{
                        "x_top_left": x0,
                        "y_top_left": y0,
                        "width": w,
                        "height": h
                    }}
                )
        
        row_list = self.size_filter(row_list)
        return row_list

    def size_filter(self, row_list):
        return [row for row in row_list if row['segment']["width"] >= 2 and row['segment']["height"] >= 2]
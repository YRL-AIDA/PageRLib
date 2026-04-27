from typing import Dict, List
from .base_physical_element import PhysicalElement, ImageSegment
from .row import Row
import cv2
import numpy as np

class Image(PhysicalElement):
    def __init__(self, segment:ImageSegment=None, data:Dict=None, **kwargs):
        if segment is None and 'array' in data:
            h, w = data['array'].shape[:2]
            segment=ImageSegment(x_top_left=0, y_top_left=0, x_bottom_right=w, y_bottom_right=h)
        super().__init__(segment=segment, data=data)
        self.name_children = None
        if "path" in self.data:
            Warning("Image path is not None")
        if "array" in self.data:
            Warning("Image array is not None")

    
    @staticmethod
    def get_none():
        im = ImageSegment(0,0,1,1)
        return Image(im, None)
    
    @property
    def text(self):
        # Возможно сделать описание
        return ""
    
    @property
    def path(self):
        if "path" in self.data:
            return self.data["path"]
        return None
    
    @property
    def img(self):
        if "array" in self.data:
            return self.data["array"]
        return None
    
    def set_img(self, img_rgb):
        self.data['array'] = img_rgb

    @staticmethod
    def read_img(path=None):
        
        if path is None:
            raise Exception("Path is None (self.path?)")
        
        with open(path, "rb") as f:
            chunk = f.read()
        chunk_arr = np.frombuffer(chunk, dtype=np.uint8)
        img_bgr = cv2.imdecode(chunk_arr, cv2.IMREAD_COLOR)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return img_rgb
    
    def _get_children_from_dict_list(self, dict) :
        # Нет элементов
        return None 

    def __repr__(self):
        return f"<image: '{self.path}', segment: {self.segment.__repr__()}>"
    

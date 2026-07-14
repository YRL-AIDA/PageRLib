from .font_identifier import load_model, row_to_vec

from ..base_page_extractor import BasePageExtractor
from pagerlib.dtypes import PageRDF, Page
from PIL import Image
import cv2

SIZES  = (512, 32, 16)
class FontEmbExtractor(BasePageExtractor):
    def __init__(self, size=512):
        if not size in SIZES:
            raise Exception(f"Exists only {SIZES}")
        self.size = size
        self.model = load_model(size)
        super().__init__()
        

    def page_extract(self, page:Page):
        
        image = page.children[0].data['array']
        for region in page.children:
            if region.children is None:
                continue
            for row in region.children:
                row_img = row.segment.get_segment_from_img(image)
                row_cv2 = cv2.cvtColor(row_img, cv2.COLOR_RGB2GRAY)
                pil_image = Image.fromarray(row_cv2)
                
                if row.data is None:
                    row.data = {}
                vec = row_to_vec(self.model, pil_image).numpy()
                row.data['font_vec'] = vec
       

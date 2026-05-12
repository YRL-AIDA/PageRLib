from ..base_page_extractor import BasePageExtractor
from pagerlib.dtypes import PageRDF, Image, Page
from pdf2image import convert_from_path
import numpy as np
import cv2

class PDFIMGExtractor(BasePageExtractor):
    def page_extract(self, page:Page):
        resized_img = cv2.resize(page.data['array'], (page.segment.width, page.segment.height))
        img = Image(data={'array': resized_img})
        page.children = [img] + page.children

    def extract(self, prdf: PageRDF):
        pil_images = convert_from_path(prdf.data['path'])
        for page, pil in zip(prdf.data['pages'], pil_images):
            if page.data is None:
                page.data = {}
            page.data['array'] = np.array(pil)
        super().extract(prdf)
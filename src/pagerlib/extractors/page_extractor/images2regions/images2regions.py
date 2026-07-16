"""Images2RegionsExtractor — applies Tesseract OCR to all Image objects with pixel data."""

from ..base_page_extractor import BasePageExtractor
from pagerlib.dtypes import Page, Image
from .image2words import Image2Words


class Images2RegionsExtractor(BasePageExtractor):
    """Применяет Tesseract OCR ко всем Image с пиксельными данными в PageRDF."""

    def __init__(self, conf: dict = None):
        super().__init__()
        self.image2words = Image2Words(conf=conf)

    def page_extract(self, page: Page):
        images = [child for child in page.children if isinstance(child, Image)]
        non_images = [child for child in page.children if not isinstance(child, Image)]
        print(images)
        new_regions = []
        for image in images:
            if image.data and image.data.get("array") is not None:
                region = self.image2words.get_region(image)
                new_regions.append(region)

        page.children = non_images + new_regions

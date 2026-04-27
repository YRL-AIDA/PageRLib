from pagerlib.dtypes import PageRDF
from pagerlib.dtypes import Page, Image
from pagerlib.dtypes import ImageSegment
import shutil

def read_image(method, path):
    if method == 'tesseract':
        tesseract_path = shutil.which("tesseract")
        if tesseract_path is None:
            raise Exception("Tesseract is not installed")
        from .image2words import Image2Words
        tesseract_reader = Image2Words()
        array = Image.read_img(path)
        
        image = Image(
            data={"array": array, "path": path}
        )
        text_region = tesseract_reader.get_region(image)
        page = Page(children=[image, text_region])
        prdf = PageRDF()
        prdf.data["pages"] = [page]
        return prdf

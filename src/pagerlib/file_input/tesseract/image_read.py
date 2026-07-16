from pagerlib.dtypes import PageRDF
from pagerlib.dtypes import Page, Image
import shutil


def read_image(method, path):
    if method == 'tesseract':
        tesseract_path = shutil.which("tesseract")
        if tesseract_path is None:
            raise Exception("Tesseract is not installed")
        array = Image.read_img(path)
        image = Image(data={"array": array, "path": str(path)})
        page = Page(children=[image])
        prdf = PageRDF()
        prdf.data["pages"] = [page]
        prdf.metadata["file_type"] = "image"
        return prdf

from pathlib import Path
from .pdf_as_json_model import read_pdf
from ..dtypes import PageRDF


class FileInput:
    def __init__(self, *args):
        self.pdf_method = "miner"
        self.image_method = "tesseract"
        if "image_method" in args:
            self.image_method = args["image_method"]
        if "pdf_method" in args:
            self.pdf_method = args["pdf_method"]


    def __call__(self, path:Path|str):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"{path} is not a file")
        
        suffix = path.suffix.lower()
        if suffix in (".pdf", ):
            return self.pdf_reader(path)
        elif suffix in (".jpg", ".jpeg", ".png"):
            return self.image_reader(path)
        

    def pdf_reader(self, path):
        prdf = read_pdf(self.pdf_method, path)
        return prdf


    def image_reader(self, path):
        raise ValueError("no set Tesseract")
        
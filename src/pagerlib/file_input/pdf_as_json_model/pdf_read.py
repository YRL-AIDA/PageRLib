from pagerlib.dtypes import PageRDF
from pagerlib.dtypes import Page, Region, Image
from pagerlib.dtypes import ImageSegment

def read_pdf(method, path):
    if method == 'miner':
        from .miner_pdf_model import MinerPDFModel
        miner = MinerPDFModel()
        miner.read_from_file(path)
        miner.extract()
        pdf_json = miner.to_dict()
        pages = []
        for page_json in pdf_json['pages']:
            h, w = page_json["height"], page_json["width"]
            no_text_regions = [Image(ImageSegment(dict_p_size=image['segment']), {}) for image in  page_json['images']]
            text_regions = []
            if len(page_json["rows"]) != 0:
                reg = Region.get_none()
                reg.from_dict({"rows":page_json["rows"]}) 
                text_regions.append(reg)   
            regions = no_text_regions + text_regions
            if len(regions) == 0:
                continue
            page = Page(segment=ImageSegment(0, 0, w, h), children=regions)
            
            pages.append(page)
        prdf = PageRDF()
        prdf.data["pages"] = pages
        return prdf

    elif method == 'precision':
        from .precision_pdf_model import PrecisionPDFModel
        precision = PrecisionPDFModel()
        precision.read_from_file(path)
        precision.extract()
        return precision.to_dict()
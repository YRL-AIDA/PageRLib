from pdfminer.layout import LAParams

from ..base_pdf_as_json_model import BasePDFasJsonModel
from .extractor import PDFStructureExtractor


class MinerPDFModel(BasePDFasJsonModel):
    def __init__(self, conf=None) -> None:
        if conf is None:
            conf = {}
        laparams = LAParams(
            line_margin=0.5, word_margin=0.1, char_margin=2.0, boxes_flow=0.5)
        debug_curves = conf.pop('debug_curves', False)
        conf['extractor'] = PDFStructureExtractor(laparams, debug_curves=debug_curves)
        super().__init__(conf)

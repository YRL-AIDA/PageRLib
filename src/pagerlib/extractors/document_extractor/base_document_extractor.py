from abc import ABC, abstractmethod
from pagerlib.dtypes import PageRDF


class BaseDocumentExtractor(ABC):

    @abstractmethod
    def document_extract(self, prdf: PageRDF):
        pass

    def extract(self, prdf: PageRDF):
        prdf.data['toc'] = self.document_extract(prdf)

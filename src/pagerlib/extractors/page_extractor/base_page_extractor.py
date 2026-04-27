from abc import ABC, abstractmethod
from pagerlib.dtypes import PageRDF
from pagerlib.utils import RegionSorterCutXYExtractor

sorter = RegionSorterCutXYExtractor()

class BasePageExtractor(ABC):

    @abstractmethod
    def page_extract(self, page):
        pass

    def extract(self, prdf: PageRDF):
        for page in prdf.data['pages']:
            self.page_extract(page)
            sorter(page)
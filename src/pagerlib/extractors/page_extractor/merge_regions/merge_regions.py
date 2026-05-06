from ..base_page_extractor import BasePageExtractor
from .merge_segment import merge_segment
from pagerlib.dtypes import Page, Region, Row, ImageSegment
from typing import List, Dict
from collections import Counter

class MergeRegion(BasePageExtractor):
    def page_extract(self, page:Page):
        text_regions = [region for region in page.children if region.children is not None]
        no_text_regions = [region for region in page.children if region.children is None]
        new_regions = self.merge(text_regions)
        page.children = no_text_regions+new_regions

    def merge(self, regions: List[Region]) -> List[Region]:
        segs = [reg.segment for reg in regions]
        new_segs: Dict[int, List[int]] = dict()
        index_segs = merge_segment(segs)
        
        for ind_seg, ind_new_seg in enumerate(index_segs):
            if ind_new_seg in new_segs.keys():
                new_segs[ind_new_seg] = new_segs[ind_new_seg]+[ind_seg]
            else:
                new_segs[ind_new_seg] = [ind_seg]
        new_regions = []
        for segs_in_regions in new_segs.values():
            rows: List[Row] = []
            segment:ImageSegment = segs[segs_in_regions[0]]
            segment.set_segment_max_segments([segs[ind] for ind in segs_in_regions])
            label = self.get_label([regions[i].data['label'] for i in segs_in_regions])
            for ind in segs_in_regions:
                rows += regions[ind].children
            new_regions.append(Region(children=rows, data={'label': label}))
        return new_regions 
    
    def get_label(self, labels):
        c = Counter(sorted(labels))
        return c.most_common(1)[0][0]
        


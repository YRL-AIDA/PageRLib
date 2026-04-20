from typing import Dict, List
from .base_physical_element import PhysicalElement, ImageSegment
from .region import Region


class Page(PhysicalElement):
    def __init__(self, children:List[Region], segment:ImageSegment=None, data:Dict=None,**kwargs):
        super().__init__(segment=segment, children=children, data=data, name_children="regions")
    
    @staticmethod
    def get_none():
        im = ImageSegment(0,0,1,1)
        return Page([], im, None)
    
    @property
    def text(self):
        return "\n".join([word.text for word in self.children])
    
    def _get_children_from_dict_list(self, dict) :
        reg_list =[Region(segment=self._get_segment(dict_segment=dict_region["segment"]), 
                         data=dict_region["data"] if "data" in dict_region else None,
                         children=dict_region["rows"]) for dict_region in dict]
        return reg_list 

    def __repr__(self):
        return f"<page text:  '{self.text[:50]} ...',  segment: {self.segment.__repr__()} (rows: {len(self.children)})>"
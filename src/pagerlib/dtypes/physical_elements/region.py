from typing import Dict, List
from .base_physical_element import PhysicalElement, ImageSegment
from .row import Row

class Region(PhysicalElement):
    def __init__(self, children:List[Row], segment:ImageSegment=None, data:Dict=None, **kwargs):
        super().__init__(segment=segment, children=children, data=data, name_children="rows")
    
    @staticmethod
    def get_none():
        im = ImageSegment(0,0,1,1)
        return Region([], im, None)
    
    @property
    def text(self):
        return "\n".join([word.text for word in self.children])
    
    def _get_children_from_dict_list(self, dict) :
        row_list =[Row(segment=self._get_segment(dict_segment=dict_row["segment"]), 
                         data=dict_row["data"] if "data" in dict_row else None,
                         children=dict_row["words"]) for dict_row in dict]
        return row_list 

    def __repr__(self):
        return f"<region text: '{self.text}', segment: {self.segment.__repr__()} (rows: {len(self.children)})>"
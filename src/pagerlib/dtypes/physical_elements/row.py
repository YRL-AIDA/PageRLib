from typing import Dict, List
from .base_physical_element import PhysicalElement, ImageSegment
from .word import Word

class Row(PhysicalElement):
    def __init__(self, children:List[Word], segment:ImageSegment=None, data:Dict=None, **kwargs):
        super().__init__(segment=segment, children=children, data=data, name_children="words")

    @staticmethod
    def get_none():
        im = ImageSegment(0,0,1,1)
        return Row([], im, None)
    
    @property
    def text(self):
        return " ".join([word.text for word in self.children])
    
    def _get_children_from_dict_list(self, dict) :
        word_list =[]
        for word_json in dict:
            data = word_json["data"] if "data" in word_json else {
                "text": word_json["text"]
            }
            if "font" in word_json:
                data["font"] = word_json["font"]
            word_list.append(Word(segment=self._get_segment(word_json["segment"]), data=data)) 
        word_list.sort(key=lambda x: x.segment.x_top_left)       
        return word_list 

    def __repr__(self):
        return f"<row text: '{self.text}', segment: {self.segment.__repr__()} (words: {len(self.children)})>"
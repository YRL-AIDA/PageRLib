from typing import Dict
from .base_physical_element import PhysicalElement, ImageSegment


class Word(PhysicalElement):
    def __init__(self, segment:ImageSegment=None, data:Dict=None, **kwargs):
        super().__init__(segment=segment, data=data,)
        self.name_children = None

    @staticmethod
    def get_none():
        im = ImageSegment(0,0,1,1)
        return Word(im, None)

    @property
    def text(self):
        return self.data["text"] if "text" in self.data else ""
    
    def _get_children_from_dict_list(self, dict) :
        # Нет посимвольной обработки
        return None 

    def __repr__(self):
        return f"<word text: '{self.text}', segment: {self.segment.__repr__()} (chars: {len(self.text)})>"
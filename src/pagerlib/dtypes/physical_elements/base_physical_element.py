from abc import ABC, abstractmethod
from typing import List, Dict
from ..image_segment import ImageSegment

class PhysicalElement(ABC):
    def __init__(self, segment:ImageSegment=None, children:List["PhysicalElement"]=None, 
                 data:Dict=None, name_children:str="children"):
        if children is not None and len(children) > 0 and type(children[0]) == dict:
            children = self._get_children_from_dict_list(children)
        
        if segment is None:
            if children is None:
                raise Exception("segment and children can't be None")
            segment = self.__get_segment_from_children(children)
        if type(segment) == dict:
            segment = self._get_segment(segment)
        self.segment: ImageSegment = segment
        self.children = children
        self.data = data
        self.name_children = name_children


    def from_dict(self, dict_:Dict):
        info = dict_.copy()
        self.__init__(
            segment=info["segment"] if "segment" in info else None,
            children=info[self.name_children],
            data=info["data"] if "data" in info else None,
            name_children=self.name_children
        )

    @property
    @abstractmethod
    def text(self):
         pass
    
    @abstractmethod
    def _get_children_from_dict_list(self, dict):
        pass

    def to_dict(self):
        info =  {
            "segment": self.segment.get_segment_p_size(),
            "data": self.data,
        }
        if not self.children is None:
            info[self.name_children] = self._get_dict_from_children()
        return info

    def _get_dict_from_children(self):
        if self.children is None:
            return {}
        return [child.to_dict() for child in self.children]


    def __get_segment_from_children(self, children:List["PhysicalElement"]):
        if len(children) == 0:
            raise Exception("children can't be empty")
        
        segments = [child.segment for child in children]
        base_segment = segments[0].copy() 
        base_segment.set_segment_max_segments(segments)
        return base_segment
    
    def _get_segment(self, dict_segment):
        return ImageSegment(dict_p_size = dict_segment) if "width" in dict_segment else ImageSegment(dict_2p = dict_segment)
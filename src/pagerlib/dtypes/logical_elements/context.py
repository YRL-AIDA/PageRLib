from pagerlib.dtypes import Region
from typing import  List

class Context:
    def __init__(self, childrens:List[Region]):
        self.children = childrens

    def to_dict(self):
        return {
            'regions': [r.to_dict() for r in self.children]
        }
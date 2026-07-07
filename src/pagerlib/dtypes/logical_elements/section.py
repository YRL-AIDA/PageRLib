from typing import List
from .context import Context
from pagerlib.dtypes import Region

class Section:
    def __init__(self, title:Region|None, level=0):
        self.title = title
        self.level = level
        self.children: List['Section', Context] = []

    
    def add_context(self, reg:Region):
        for r in reversed(self.children):
            if isinstance(r, Context):
                r.children.append(reg)
                return
        self.children.append(Context([reg]))


    def to_dict(self):
        return {
            "level": self.level,
            "title": self.title.to_dict(),
            "children": [c.to_dict() for c in self.children]
        }

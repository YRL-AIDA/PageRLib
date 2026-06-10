class _MergedElement:
    __slots__ = ("bbox", "name")

    def __init__(self, bbox, name=None):
        self.bbox = bbox
        self.name = name


class _PreMergedBox:
    """Wrapper for grid-BFS pre-merge groups — gets padded in overlap merge.
    _MergedElement is reserved for final merged results (no further padding)."""
    __slots__ = ("bbox", "name")

    def __init__(self, bbox, name=None):
        self.bbox = bbox
        self.name = name

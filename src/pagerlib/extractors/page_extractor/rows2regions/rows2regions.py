from .rows2region_glam_20260225 import get_load_model
from .rowsGLAM_tokenizer_20260225 import RowGLAMTokenizer
from pagerlib.dtypes import Page, Region, ImageSegment
from pagerlib.dtypes.relationship import Graph
from ..base_page_extractor import BasePageExtractor
import numpy as np
import torch

CLASSES = {1: 'text', 2: 'header', 3: 'text', 4: 'table', 5: 'figure', 0: 'other'}
class Rows2Regions(BasePageExtractor):
    def __init__(self):
        self.model = get_load_model()
        self.tokenizer = RowGLAMTokenizer()

    def page_extract(self, page:Page):
        text_regions = [region for region in page.children if region.children is not None]
        no_text_regions = [region for region in page.children if region.children is None]
        
        rows = [{"text": row.text,
                 "segment": row.segment.get_segment_2p(),
                 "words": [word.to_dict() for word in row.children]
                } for region in text_regions for row in region.children]
        count_rows = len(rows)
        if  count_rows == 0:
            region_list = []
        elif count_rows == 1:
            region_list = [Region(children=rows, data={'label': CLASSES[0]})]
        else:
            region_list = self.get_region(rows)
        page.children = no_text_regions+region_list


    def get_region(self, rows_json):
        graph_dict_torch = self.tokenizer(rows_json)
        
        with torch.no_grad():
            result = self.model(graph_dict_torch)
        result['deleted_edges'] = result['E_pred'] < 0.5
        
        graph = graph_dict_torch['inds']
        deleted_edges = result['deleted_edges']
        node_classes = result['node_classes']
        regions = self.regions_from_graph(rows_json, graph, deleted_edges, node_classes)
        return regions
    

    def regions_from_graph(self, rows_json, graph, deleted_edges, node_classes):
        graph_ = Graph()
        regions = []
        
        for row_json in rows_json:
            segment = ImageSegment(dict_2p=row_json['segment'])
            xc, yc = segment.get_center()
            graph_.add_node(xc, yc)

        for node_i, node_j, ind in zip(graph[0], graph[1], deleted_edges):
            if not ind:
                graph_.add_edge(node_i+1, node_j+1)
        for reg in graph_.get_related_graphs():
            indexes = [node.index-1 for node in reg.get_nodes()]
            row_classes  = np.array([node_classes[i].detach().numpy() for i in indexes])
            lable = CLASSES[np.argmax(row_classes.mean(axis=0))]
            
            regions.append(Region(children=[rows_json[i] for i in indexes],data={'label': lable}))
        return regions
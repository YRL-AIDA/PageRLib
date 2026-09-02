from .rows2region_glam_20260826 import get_load_model
from .rowsGLAM_tokenizer_20260826 import RowGLAMTokenizer
from pagerlib.dtypes import Page, Region, ImageSegment, Image, Row
from pagerlib.dtypes.relationship import Graph
from ..base_page_extractor import BasePageExtractor
import numpy as np
import torch

CLASSES = {1: 'text', 2: 'header', 3: 'list', 4: 'table', 5: 'figure', 0: 'other'}
class Rows2Regions(BasePageExtractor):
    def __init__(self):
        self.model = get_load_model()
        self.tokenizer = RowGLAMTokenizer()

    def page_extract(self, page:Page):
        if not isinstance(page.children[0], Image):
            raise Exception('USE: ' \
            'from pagerlib.extractors.page_extractor import PDFIMGExtractor' \
            'pdf_add_img.extract(prdf)')
        pdf_as_img_region = page.children[0]
        pdf_img = pdf_as_img_region.data['array']
        text_regions = [region for region in page.children[1:] if region.children is not None]
        no_text_regions = [region for region in page.children[1:] if region.children is None]
        
        rows = [{"text": row.text,
                 "segment": row.segment.get_segment_p_size(),
                 "words": [word.to_dict() for word in row.children]
                } for region in text_regions for row in region.children]
        images = [{"text": region.text,
                   "segment": region.segment.get_segment_p_size()
                } for region in no_text_regions ]
        rows = self.fix_row_this_image(rows, images)
        count_rows = len(rows)
        if  count_rows == 0:
            region_list = []
        elif count_rows == 1:
            region_list = [Region(children=rows, data={'label': CLASSES[0]})]
        else:
            region_list = self.get_region(rows,pdf_img)
        page.children = region_list


    def get_region(self, rows_json, pdf_img):
        graph_dict_torch = self.tokenizer(rows_json, pdf_img)
        
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
            segment = ImageSegment(dict_p_size=row_json['segment'])
            xc, yc = segment.get_center()
            graph_.add_node(xc, yc)

        for node_i, node_j, ind in zip(graph[0], graph[1], deleted_edges):
            if not ind:
                graph_.add_edge(node_i+1, node_j+1)
        for reg in graph_.get_related_graphs():
            indexes = [node.index-1 for node in reg.get_nodes()]
            row_classes  = np.array([node_classes[i].detach().numpy() for i in indexes])
            lable = CLASSES[np.argmax(row_classes.mean(axis=0))]
            rows = [rows_json[i] for i in indexes]
            clean_rows = [row for row in rows if 'words' in row]
            segment = ImageSegment(0,0,1,1)
            segment.set_segment_max_segments([ImageSegment(dict_p_size=json_row['segment']) for json_row in rows])
            if len(clean_rows) == 0:     
                regions.append(Image(segment=segment, data={'label': 'figure'}))
            else:
                regions.append(Region(segment=segment, children=clean_rows, data={'label': lable}))
        return regions

    def fix_row_this_image(self, rows, image_rows):
        def get_rows(dict_row):
            dict_row['words'] = [{"segment": w['segment'],
                                 "text": w['data']['text'],
                                 "font": w['data']['font']} for w in dict_row['words']] if 'words' in dict_row else []
           
            row = Row.get_none()
            row.from_dict(dict_row)
            return row
            # r.from_dict(dict_row)
            # return r
        
        img_rows = [get_rows(row) for row in image_rows]
        bool_matrix = np.array([
                        [
                            img_row_i.segment.is_intersection(img_row_j.segment)
                        for img_row_j in img_rows] 
                    for img_row_i in img_rows])
        new_bool_matrix = bool_matrix == None
        while (new_bool_matrix != bool_matrix).any():
            new_bool_matrix = bool_matrix.copy()
            bool_matrix = bool_matrix@bool_matrix
                        
        inds = np.array([i for i in range(len(img_rows))])

        blocks = []
        for _ in range(len(inds)):
            if len(inds) < 1:
                break
            i = np.argmin(inds)
            neig = inds[bool_matrix[i]]
            inds = inds[~bool_matrix[i]]
            blocks.append(neig)
            bool_matrix = bool_matrix[~bool_matrix[i], : ][:, ~bool_matrix[i]] 
            
        def get_row(rows):
            img_seg = ImageSegment(0,0,1,1)
            img_seg.set_segment_max_segments([r.segment for r in rows])
            dict_row = {'segment': img_seg.get_segment_p_size(), 'text':' ', 'words':None}
            row = Row.get_none()
            row.from_dict(dict_row)
            return row

        img_rows = [
            get_row([img_rows[int(b)] for b in block])
            for block in blocks
        ]
        new_rows= []
        array_rows = [get_rows(row) for row in rows]
        for row in array_rows:
            include=True
            for img_row in img_rows:
                if row.segment.is_intersection(img_row.segment):
                    img_row.segment.set_segment_max_segments([img_row.segment, row.segment])
                    include=False
            if include:  
                new_rows.append(row)
        
        rows = new_rows+img_rows       
        return [row.to_dict() for row in rows]
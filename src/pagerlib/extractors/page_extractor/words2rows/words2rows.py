from .words2rows_glam_20260113 import get_load_model
from .wordGLAM_tokenizer_20260113 import WordGLAMTokenizer
from pagerlib.dtypes import Page, Region, Row, Word
from pagerlib.dtypes.relationship import Graph
from ..base_page_extractor import BasePageExtractor
import numpy as np
from typing import List

class Words2Rows(BasePageExtractor):
    def __init__(self, conf={}):
        self.words2rowsGLAM_tokenizer = WordGLAMTokenizer()
        self.words2rowsGLAM = get_load_model()

    def page_extract(self, page:Page):
        text_regions = [region for region in page.children if region.children is not None]
        no_text_regions = [region for region in page.children if region.children is None]
        
        words = [word for region in text_regions for row in region.children for word in row.children]
        words_json = [{"text": word.text,
                 "segment": word.segment.get_segment_2p(),
                } for word in words]
        count_rows = len(words)
        if  count_rows == 0:
            row_list = []
        elif count_rows == 1:
            row_list = [Row(children=words)]
        else:
            row_list = self.get_row(words_json, words)
        page.children = no_text_regions+[Region(children=row_list)]

    def get_row(self, words_json, words):
        graph_dict_torch = self.words2rowsGLAM_tokenizer(words_json)
        if graph_dict_torch['N'] < 2 or len(graph_dict_torch['inds'][0]) < 2:
            return [{'words': words_json}]

        result = self.words2rowsGLAM(graph_dict_torch)
        result['deleted_edges'] = result['E_pred'] > 0.5
        
        graph = graph_dict_torch['inds']
        deleted_edges = result['deleted_edges']
        
        rows = self.rows_from_graph(words, graph, deleted_edges)
        return rows
    

    def rows_from_graph(self, words:List[Word], graph, deleted_edges):
        graph_ = Graph()
        rows = []
        
        for word in words:
            xc, yc = word.segment.get_center()
            graph_.add_node(xc, yc)

        for node_i, node_j, ind in zip(graph[0], graph[1], deleted_edges):
            if not ind:
                graph_.add_edge(node_i+1, node_j+1)

        for reg in graph_.get_related_graphs():
            indexes = [node.index-1 for node in reg.get_nodes()]
            word_from_row = [words[i] for i in indexes]
            rows.append(Row(children=word_from_row))
        return rows
    


# def obj_words2rows(words):
#     words_dict = [w.to_dict() for w in words] 
#     rows_dict = dict_words2rows(words_dict)
#     return [Row(row_dict) for row_dict in rows_dict]
    

# def dict_words2rows(dict_words):
#     converter = Words2Rows()
#     model_rows = RowsModel()
#     model_words = WordsModel()

#     model_words.set_words_from_dict(dict_words)
#     converter.convert(model_words, model_rows)
#     rows = model_rows.to_dict()['rows']
#     return rows
from pagerlib.extractors.page_extractor.font_emb_extractor.font_identifier import load_model, row_to_vec
from pagerlib.dtypes import ImageSegment
from pagerlib.dtypes import ImageSegment

import cv2
from PIL import Image
import numpy as np
from typing import Dict, List
from abc import abstractmethod
import re

import torch
torch.sparse.check_sparse_tensor_invariants.disable()

def graph_creat(segments):
    def fun_dist_bottom(seg1: ImageSegment, seg: ImageSegment):
        DIST = 3
        r1 = seg1.x_bottom_right
        r = seg.x_bottom_right
        l1 = seg1.x_top_left
        l = seg.x_top_left

        x1c, y1c = seg1.get_center()
        xc, yc = seg.get_center()
        if y1c > yc: # Только в одном направление
            return np.inf
        
        if abs(x1c-xc)+abs(y1c-yc) < DIST: # Если совпали
            return np.inf
        
        xd = min(abs(r1-r), abs(l1-l), abs(xc-x1c))
        yd = abs(y1c-yc) 
        
        if abs(r1-r) < DIST or abs(l1-l) < DIST or abs(xc-x1c) < DIST :
            return yd

        
        return xd+yd

    def fun_dist_right(seg1: ImageSegment, seg: ImageSegment):
        DIST = 3
        r1 = seg1.x_bottom_right
        r = seg.x_bottom_right
        l1 = seg1.x_top_left
        l = seg.x_top_left

        x1c, y1c = seg1.get_center()
        xc, yc = seg.get_center()
        if x1c > xc: # Только в одном направление
            return np.inf

        
        if abs(x1c-xc)+abs(y1c-yc) < DIST: # Если совпали
            return np.inf
        
        xd = min(abs(r1-l), abs(l1-r))
        yd = abs(y1c-yc) 

        h = (seg.height + seg1.height)/2
        if yd > 2*h:
            return np.inf
            
        
        return xd+yd

    dists_bottom = []
    for j, seg1 in enumerate(segments):
        dist_bottom = [fun_dist_bottom(seg1, seg) for seg in segments]
        if min(dist_bottom) == np.inf:
            continue
        k = int(np.argmin(dist_bottom))
        dists_bottom.append((min(j, k), max(j, k)))

    # dists_top = [(k, j) for j, k in dists_bottom]

    dists_right = []
    for j, seg1 in enumerate(segments):
        dist_right = [fun_dist_right(seg1, seg) for seg in segments]
        if min(dist_right) == np.inf:
            continue
        k = int(np.argmin(dist_right))
        dists_right.append((min(j, k), max(j, k)))

    # dists_left = [(k, j) for j, k in dists_right]

    all_edges = dists_bottom + dists_right
    all_edges = list(set(all_edges))
    return all_edges

class RowGLAMTokenizer():
    def get_name(self):
        return "RowGLAM"
    
    def __call__(self, rows_json, pdf_img):
        A = self.get_A(rows_json)
        node_features = self.get_node_features(rows_json, pdf_img)
        edge_features = self.get_edge_features(A, rows_json, pdf_img)
        json_info =  {
            'A': A,
            'node_features': node_features,
            'edge_features': edge_features
        }
        return self.get_tensor_from_graph(json_info)

    def get_A(self, rows_json):
        
        edges = graph_creat([ImageSegment(dict_2p=row_json['segment']) for row_json in rows_json])

        A1, A2 = [], []
        for a1, a2 in edges:
            A1.append(a1)
            A2.append(a2)
        index = np.argsort(A1)
        A1_ = [A1[i] for i in index]
        A2_ = [A2[i] for i in index]
    
        return [A1_, A2_]
    
    def get_node_features(self, rows_json, pdf_img):
        if len(rows_json) == 0:
            return [[]]
        page_h, page_w = pdf_img.shape[:2]
        
        segs = [ImageSegment(dict_2p=row_json['segment']) for row_json in rows_json]
        page_x_min = min([seg.x_top_left for seg in segs])
        page_y_min = min([seg.y_top_left for seg in segs])
        page = [page_h, page_w, page_x_min, page_y_min]
        rows_texts = [' '.join(w.get('data').get('text', '') for w in r.get('words', [])) for r in rows_json]
        dot_vec = np.array([self.get_vec_end_char(r) for r in rows_texts])
        list_ind_vec = np.array([self.get_vec_list(r) for r in rows_texts])
        super_vec = np.array([self.get_vec_supper(r) for r in rows_texts])
        coord_vec = np.array([self.get_vec_coord(seg, page) for seg in segs])
        heuristics_vec = np.array([self.get_vec_heuristics(r_json) for r_json in rows_json])
        nodes_feature = np.concat([coord_vec,  dot_vec, super_vec, list_ind_vec, heuristics_vec], axis=1)
        return nodes_feature.tolist()
    
    def get_vec_end_char(self, text):
        dots = (".", ",", ";", ":", '?', '!')
        text_ = text.lstrip()
        if len(text_) == 0:
            return [0 for _ in dots]
        
        return [1.0 if text_[-1] == dot else 0.0 for dot in dots ] 
    
    def get_dict_vec(self):
        return {
            "x_top_left": [0],
            "x_bottom_right": [1],
            "width": [2],
            "y_top_left":[3],
            "y_bottom_right": [4],
            "height" : [5],
            "norm_geom": [6, 7, 8, 9],
            "dot_vec": [10, 11, 12, 13, 14, 15],
            "super_vec": [16],
            "list_ind_vec": [17],
            "heuristics_vec": [18, 19, 20]
        }

    def get_edge_features(self, A, rows_json, pdf_img):
        edges_featch = []
        for i, j in zip(A[0], A[1]):
            r1 = ImageSegment(dict_2p= rows_json[i]['segment'])
            r2 = ImageSegment(dict_2p= rows_json[j]['segment'])
            x1, y1 = r1.get_center()
            x2, y2 = r2.get_center()

            edges_featch.append([r1.get_angle_center(r2), r1.get_min_dist(r2), abs(x1-x2), abs(y1-y2)])
        # print(edges_featch)
        return edges_featch
    
    def get_tensor_from_graph(self, graph):
        i = graph["A"] # треугольная
        index_for_mtrix = [i[0]+i[1], i[1]+i[0]] 
        v_in = [1 for e in index_for_mtrix[0]]
        y = graph["edge_features"]
        # for yi in y:
        #     yi[0] = 1.0 if yi[0] > 0.86 else 0.0
        x = graph["node_features"]
        N = len(x)
        
        X = torch.tensor(data=x, dtype=torch.float32)
        Y = torch.tensor(data=y, dtype=torch.float32)
        sp_A = torch.sparse_coo_tensor(indices=index_for_mtrix, values=v_in, size=(N, N), dtype=torch.float32)
        
        return {
            "N": N,
            "X": X,
            "Y": Y,
            "sp_A": sp_A,
            "inds": i
        }
    
    def get_vec_heuristics(self, row):
        text = ' '.join(w.get('data').get('text', '') for w in row.get('words', []))
        text_size = len(text)
        if text_size == 0:
            return [0, 0, 0]
        seg = ImageSegment(dict_2p=row['segment'])
        m = seg.width/seg.height
        digit_count = sum(char.isdigit() for char in text)
        return [text_size/m, digit_count/text_size, np.log(1+len(text))]

    def get_vec_supper(self, row_text):
        if len(row_text) == 0:
            return [0]
        isup = sum(1 for char in row_text if char.isupper())/len(row_text)
        return [isup]
        
    def get_vec_list(self, row_text):
        patterns = [
                r'\b(\d+[.)])\s+',  # 1) 2. 15)
                r'\b([a-zA-Z][.)])\s+',  # a) B.
                r'\b([IVXLCDM]+[.)])\s+',  # XIX. VII)
                r'\[\d+\]',  # [5]
                r'\(\d+\)',  # (3)
                r'(?:^|\s)([•▪▫○◆▶➢✓-])\s+',  # Спецсимволы: • Item, ▪ Subitem
                r'\*{1,}\s+',  # Звездочки: **
                r'\b\d+\.\d+\b',  # Многоуровневые: 1.1, 2.3.4
                r'\b\d+-\w+\)',  # Комбинированные: 1-a), 5-b.
                r'\b(?:Item|Пункт)\s+\d+:\s+',  # Явные указатели: Item 5:
                r'(?:^|\s)\u2022\s+',  # Юникод-символы: •
                r'\[[A-Z]\]',  # Буквы в скобках: [A]
                r'\b\d{2,}\.\s+',  # Номера с ведущими нулями: 01.
                r'#\d+\b',  # Хештег-нумерация: #5
                r'\b\d+\s*[-–—]\s+',  # Тире-разделители: 5 -
                r'\b\d+/\w+\b',  # Слэш-нумерация: 1/a
                r'<\d+>',  # Угловые скобки: <3>
                r'\b[A-Z]\d+\)',  # Буква+число: A1)
                r'\b(?:Step|Шаг)\s+\d+\b',  # Шаги: Step 3
                r'\d+[.)]\s*-\s+',  # Комбинированные с тире: 1). -
                r'\b[А-Яа-я]\s*[).]\s+',  # а) б. кириллица
                r'\b\d+[.:]\d+\)',  # 1:2) вложенность
                r'\d+\s*→\s+',  # 1 → со стрелкой
                r'\b\d+\.?[a-z]\b',  # Буквенные подуровни: 1a
                r'\b[A-Z]+-\d+\b'  # Код-номера: ABC-123
            ]
        flag = False
        if len(row_text) < 2:
            return [0]
        for pattern in patterns:
            if bool(re.search(pattern, row_text[:len(row_text)//2], flags=re.IGNORECASE)):
                flag = True
                break
        list_mark = 1 if flag else 0
        return [list_mark]

    def get_vec_coord(self, seg, page):
        page_h, page_w, page_x_min, page_y_min = page 
        return [seg.x_top_left, seg.x_bottom_right, seg.width, seg.y_top_left, seg.y_bottom_right, seg.height,
                seg.y_top_left/page_h, seg.x_top_left/page_w, (seg.y_top_left-page_y_min)/page_h, (seg.x_top_left-page_x_min)/page_w]

class FontRowGlAMTokenizer(RowGLAMTokenizer):

    def get_dict_vec(self) -> Dict[str, List[int]]:
        dict_feature = super().get_dict_vec()
        list_feature = []
        for list_f in dict_feature.values():
            list_feature += list_f
        N = len(list_feature)
        dict_feature['font_width'] = [N + 0]
        dict_feature['font_italic'] = [N + 1]
        dict_feature['font_size'] = [N + 2]
        return dict_feature

    def get_name(self) -> str:
        return "Font Tokenizer"

    def get_node_features(self, rows_json, pdf_img):
        old_feature = np.array(super().get_node_features(rows_json, pdf_img))
        font_feature_vec = np.array([self._get_vec_font_safe(r_json, pdf_img) for r_json in rows_json])
        nodes_feature = np.concat([old_feature, font_feature_vec], axis=1)
        return nodes_feature.tolist()

    def _get_vec_font_safe(self, row, pdf_img):
        try:
            vec = self.get_vec_font(row, pdf_img)
            return vec
        except (KeyError, Exception):
            return np.zeros(self.get_num_font_features(), dtype=np.float32)

    @abstractmethod
    def get_vec_font(self, row, pdf_img):
        pass

    @abstractmethod
    def get_num_font_features(self) -> int:
        pass

class FontEmbRowGLAMTokenizer(FontRowGlAMTokenizer):

    def __init__(self):
        self._size = 32
        self._model = None
        super().__init__()

    @property
    def _lazy_model(self):
        if self._model is None:
            self._model = load_model(self._size)
        return self._model

    def get_vec_font(self, row, pdf_img):
        seg = ImageSegment(dict_2p=row['segment'])
        row_img = seg.get_segment_from_img(pdf_img)
        row_cv2 = cv2.cvtColor(row_img, cv2.COLOR_RGB2GRAY)
        pil_image = Image.fromarray(row_cv2)
        return row_to_vec(self._lazy_model, pil_image).numpy()

    def get_num_font_features(self) -> int:
        return self._size
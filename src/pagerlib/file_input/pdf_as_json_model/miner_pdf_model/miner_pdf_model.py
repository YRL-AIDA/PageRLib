from typing import Dict, List
import logging

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextLine, LTTextLineHorizontal
from pdfminer.layout import LTChar, LAParams
from pdfminer.layout import LTImage, LTFigure, LTPage, LTRect, LTCurve, LTLine
import math
from ..base_pdf_as_json_model import BasePDFasJsonModel

# Убирает ошибку Cannot set gray non-stroke color because /'P1' is an invalid float value
logging.getLogger("pdfminer.pdfinterp").setLevel(logging.ERROR)


DPI = 72
class PDFStructureExtractor:
    def __init__(self, laparams: LAParams = None):
        """Инициализация парсера PDF"""
        self.laparams = laparams or LAParams(
            line_margin=0.5,
            word_margin=0.1,
            char_margin=2.0,
            boxes_flow=0.5,
            detect_vertical=True
        )
    
    def _pdf_to_pixel_coords(self, x, y, page_height_points, dpi=DPI):
        """
        x, y — координаты в points из PDFMiner (относительно cropbox)
        page_height_points — высота страницы в points (cropbox.y1 - cropbox.y0)
        dpi — разрешение для рендеринга
        возвращает (x_px, y_px) — пиксельные координаты с началом в верхнем левом углу
        """
        # Масштабируем в пиксели
        x_px = x * dpi / 72.0
        y_px = (page_height_points - y) * dpi / 72.0  # переворот вертикали
        return int(x_px), int(y_px)


    def _get_coords(self, bbox, page_height):
        x_pdf_bottom_left, y_pdf_bottom_left, x_pdf_top_right, y_pdf_top_right = bbox

        x0_px, y0_px = self._pdf_to_pixel_coords(x_pdf_bottom_left, y_pdf_top_right, page_height)
        x1_px, y1_px = self._pdf_to_pixel_coords(x_pdf_top_right, y_pdf_bottom_left, page_height)

        # Нормализуем координаты
        x_top_left = min(x0_px, x1_px)
        x_bottom_right = max(x0_px, x1_px)
        y_top_left = min(y0_px, y1_px)
        y_bottom_right = max(y0_px, y1_px)
        # Преобразуем координаты
        
        height = y_bottom_right - y_top_left
        width = x_bottom_right - x_top_left
        return x_top_left, x_bottom_right, width, y_top_left, y_bottom_right, height

    def extract_from_path(self, pdf_path: str) -> Dict:
        """Извлечение структуры из PDF файла"""
        result = {
            "document": pdf_path,
            "pages": [],
        }
        
        for page_num, page_layout in enumerate(extract_pages(pdf_path, laparams=self.laparams)):
            page_info = self._process_page(page_layout, page_num)
            result["pages"].append(page_info)
        return result
    
    def _process_page(self, page_layout:LTPage, page_number: int) -> Dict:
        """Обработка одной страницы"""
        page_info = {
            "number": page_number,
            "width": math.ceil(page_layout.width*DPI/72),
            "height": math.ceil(page_layout.height*DPI/72),
            "rows": [],
            "images": []  # Добавляем список для изображений
        }
        
        # Собираем все элементы страницы
        elements = []
        self._collect_elements(page_layout, elements)

        # Собираем ID визуальных потомков всех LTFigure, чтобы не дублировать
        skip_ids = set()
        for element in elements:
            if isinstance(element, LTFigure):
                children = []
                self._collect_elements(element, children)
                for c in children:
                    if isinstance(c, (LTImage, LTCurve)):
                        skip_ids.add(id(c))

        # Разделяем элементы по типам
        text_lines = []
        images = []
        page_chars = []

        for element in elements:
            if id(element) in skip_ids:
                continue
            if isinstance(element, LTTextLine):
                text_lines.append(element)
            elif isinstance(element, LTChar):
                page_chars.append(element)
            elif isinstance(element, LTImage):
                images.append(element)
            elif isinstance(element, LTFigure):
                figure_visuals = self._extract_visual_from_figure(element)
                images.extend(figure_visuals)
            elif isinstance(element, LTCurve):
                images.append(element)

        if not text_lines and page_chars:
            text_lines = self._chars_to_text_lines(page_chars)
            
        
        # Обрабатываем текстовые строки
        for text_line in text_lines:
            row_info = self._process_text_line(text_line, page_layout.height)
            if row_info and self.__is_correct_segment(row_info['segment']) and len(row_info["words"])!=0:
                page_info["rows"].append(row_info)

        page_info["rows"] = self._merge_vertical_rows(page_info["rows"])

        # Обрабатываем изображения
        page_w = math.ceil(page_layout.width * DPI / 72)
        page_h = math.ceil(page_layout.height * DPI / 72)
        visual_elements = self._merge_overlapping_images(images)
        for elem in visual_elements:
            image_info = self._process_image(elem, page_layout.height, page_w, page_h)
            if image_info and self.__is_correct_segment(image_info['segment']):
                page_info["images"].append(image_info)

        # Сортируем строки по Y координате (сверху вниз)
        page_info["rows"].sort(key=lambda x: x["segment"]["y_top_left"], reverse=False)
        
        # Сортируем изображения по Y координате (сверху вниз)
        page_info["images"].sort(key=lambda x: x["segment"]["y_top_left"], reverse=False)
        
        return page_info

    @staticmethod
    def _merge_vertical_rows(rows: List[Dict]) -> List[Dict]:
        if not rows:
            return rows
        vertical_candidates = []
        for r in rows:
            text = r.get("text", "")
            words = r.get("words", [])
            if len(text) == 1 and len(words) == 1:
                vertical_candidates.append(r)
        if len(vertical_candidates) < 2:
            return rows

        x_groups = {}
        for r in vertical_candidates:
            xc = round(r["segment"]["x_top_left"], 0)
            found = False
            for key in list(x_groups.keys()):
                if abs(key - xc) <= 3:
                    x_groups[key].append(r)
                    found = True
                    break
            if not found:
                x_groups[xc] = [r]

        merged = []
        used_indices = set()
        for xkey, group in x_groups.items():
            if len(group) < 2:
                continue
            group.sort(key=lambda r: r["segment"]["y_top_left"])
            heights = [r["segment"]["height"] for r in group]
            heights.sort()
            char_h = heights[len(heights) // 2]
            y_gaps = []
            for i in range(1, len(group)):
                prev_bottom = group[i - 1]["segment"]["y_top_left"] + group[i - 1]["segment"]["height"]
                curr_top = group[i]["segment"]["y_top_left"]
                y_gaps.append(curr_top - prev_bottom)
            if not y_gaps:
                continue
            y_gaps.sort()
            med_gap = y_gaps[len(y_gaps) // 2]
            max_gap = min(max(med_gap * 4, char_h * 0.5, 6), char_h * 1.5)
            run = [group[0]]
            for i in range(1, len(group)):
                prev_bottom = group[i - 1]["segment"]["y_top_left"] + group[i - 1]["segment"]["height"]
                curr_top = group[i]["segment"]["y_top_left"]
                gap = curr_top - prev_bottom
                if gap <= max_gap:
                    run.append(group[i])
                else:
                    if len(run) >= 3:
                        merged.append(run)
                    run = [group[i]]
            if len(run) >= 3:
                merged.append(run)

        merged_rows = []
        for run in merged:
            for r in run:
                used_indices.add(id(r))
            run.sort(key=lambda r: r["segment"]["y_top_left"])
            texts = [r["text"] for r in run]
            all_words = []
            for r in run:
                all_words.extend(r["words"])
            x0 = min(r["segment"]["x_top_left"] for r in run)
            y0 = min(r["segment"]["y_top_left"] for r in run)
            x1 = max(r["segment"]["x_top_left"] + r["segment"]["width"] for r in run)
            y1 = max(r["segment"]["y_top_left"] + r["segment"]["height"] for r in run)
            merged_rows.append({
                "segment": {
                    "x_top_left": x0,
                    "y_top_left": y0,
                    "width": x1 - x0,
                    "height": y1 - y0,
                },
                "text": "".join(texts),
                "words": all_words,
            })

        result = [r for r in rows if id(r) not in used_indices]
        result.extend(merged_rows)
        return result

    @staticmethod
    def _merge_overlapping_images(elements: List) -> List:
        if len(elements) < 2:
            return elements

        class _MergedImage:
            def __init__(self, bbox, name=None):
                self.bbox = bbox
                self.name = name

        def pad_bbox(e):
            if isinstance(e, (_MergedImage, LTImage, LTFigure)):
                return e.bbox[:]
            b = e.bbox
            return [b[0] - 2, b[1] - 2, b[2] + 2, b[3] + 2]

        while True:
            n = len(elements)
            parent = list(range(n))

            def find(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i

            def union(i, j):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj

            merged_count = 0
            for i in range(n):
                bi = pad_bbox(elements[i])
                for j in range(i + 1, n):
                    bj = pad_bbox(elements[j])
                    if bi[0] < bj[2] and bi[2] > bj[0] and bi[1] < bj[3] and bi[3] > bj[1]:
                        if find(i) != find(j):
                            union(i, j)
                            merged_count += 1

            if merged_count == 0:
                break

            groups = {}
            for i in range(n):
                root = find(i)
                groups.setdefault(root, []).append(elements[i])

            new_elements = []
            for group in groups.values():
                if len(group) == 1:
                    new_elements.append(group[0])
                else:
                    x0 = min(im.bbox[0] for im in group)
                    y0 = min(im.bbox[1] for im in group)
                    x1 = max(im.bbox[2] for im in group)
                    y1 = max(im.bbox[3] for im in group)
                    name = getattr(group[0], "name", None)
                    new_elements.append(_MergedImage((x0, y0, x1, y1), name))

            if len(new_elements) == n:
                break
            elements = new_elements

        return elements

    @staticmethod
    def _chars_to_text_line(chars):
        class _Line:
            def __init__(self, chs):
                self._chars = chs
                xs, ys = [], []
                for c in chs:
                    xs.extend([c.bbox[0], c.bbox[2]])
                    ys.extend([c.bbox[1], c.bbox[3]])
                self.x0 = min(xs) if xs else 0
                self.y0 = min(ys) if ys else 0
                self.x1 = max(xs) if xs else 0
                self.y1 = max(ys) if ys else 0

            def get_text(self):
                return "".join(c.get_text() for c in self._chars)

            def __iter__(self):
                return iter(self._chars)

        return _Line(chars)

    @staticmethod
    def _is_vertical_char(c: LTChar) -> bool:
        h = c.y1 - c.y0
        w = c.x1 - c.x0
        return h > w * 1.5 and w > 0 and not getattr(c, "upright", True)

    def _chars_to_text_lines(self, chars: List[LTChar]):
        if not chars:
            return []
        horizontal = [c for c in chars if not self._is_vertical_char(c)]
        vertical = [c for c in chars if self._is_vertical_char(c)]
        lines = []
        if horizontal:
            lines.extend(self._group_chars_by_axis(horizontal, axis="y"))
        if vertical:
            lines.extend(self._group_chars_by_axis(vertical, axis="x"))
        return lines

    def _group_chars_by_axis(self, chars: List[LTChar], axis: str):
        if axis == "y":
            key = lambda c: (c.y0, c.x0)
        else:
            key = lambda c: (c.x0, c.y0)
        sorted_chars = sorted(chars, key=key)
        result = []
        current = [sorted_chars[0]]
        for c in sorted_chars[1:]:
            prev = current[-1]
            if axis == "y":
                same_line = abs(c.y0 - prev.y0) <= 2 and abs(c.y1 - prev.y1) <= 2
            else:
                same_line = abs(c.x0 - prev.x0) <= 2 and abs(c.x1 - prev.x1) <= 2
            if same_line:
                current.append(c)
            else:
                self._split_and_add_lines(current, result, axis)
                current = [c]
        if current:
            self._split_and_add_lines(current, result, axis)
        return result

    @staticmethod
    def _split_and_add_lines(chars: List[LTChar], output: List, axis: str = "x"):
        if len(chars) <= 1:
            output.append(PDFStructureExtractor._chars_to_text_line(chars))
            return
        if axis == "y":
            sorted_chars = sorted(chars, key=lambda ch: ch.x0)
        else:
            sorted_chars = sorted(chars, key=lambda ch: ch.y1, reverse=True)
        gaps = []
        for i in range(1, len(sorted_chars)):
            if axis == "y":
                gap = sorted_chars[i].x0 - sorted_chars[i - 1].x1
            else:
                gap = (sorted_chars[i - 1].y0 - sorted_chars[i].y1)
            gaps.append(gap)
        gaps.sort()
        median_gap = gaps[len(gaps) // 2]
        threshold = max(median_gap * 3, 15)
        segment = [sorted_chars[0]]
        for i in range(1, len(sorted_chars)):
            if axis == "y":
                gap = sorted_chars[i].x0 - sorted_chars[i - 1].x1
            else:
                gap = sorted_chars[i - 1].y0 - sorted_chars[i].y1
            if gap > threshold:
                output.append(PDFStructureExtractor._chars_to_text_line(segment))
                segment = [sorted_chars[i]]
            else:
                segment.append(sorted_chars[i])
        if segment:
            output.append(PDFStructureExtractor._chars_to_text_line(segment))

    def _collect_elements(self, element, elements_list: List, stop_types=None):
        """Рекурсивный сбор всех элементов макета"""
        elements_list.append(element)

        if stop_types and isinstance(element, stop_types):
            return

        if hasattr(element, '_objs'):
            for child in element._objs:
                self._collect_elements(child, elements_list, stop_types)

    def _extract_visual_from_figure(self, figure: LTFigure) -> List:
        """Извлекает визуальные элементы из LTFigure.
        Если фигура содержит текст — возвращает отдельные изображения/кривые.
        Если только графика — возвращает фигуру целиком."""
        children = []
        self._collect_elements(figure, children)
        has_text = any(isinstance(c, (LTTextLine, LTChar)) for c in children)
        has_visual = any(isinstance(c, (LTImage, LTFigure, LTCurve)) for c in children
                         if c is not figure)
        if not has_visual:
            return []
        if has_text:
            result = []
            for c in children:
                if isinstance(c, (LTImage, LTCurve)) and not isinstance(c, LTFigure):
                    result.append(c)
            return result if result else [figure]
        return [figure]
    
    def _process_text_line(self, text_line: LTTextLine, page_height: float) -> Dict:
        """Обработка текстовой строки"""
        if not text_line.get_text().strip():
            return None
        x0, y0, x1, y1 = text_line.x0, text_line.y0, text_line.x1, text_line.y1
        x_top_left, x_bottom_right, width, y_top_left, y_bottom_right, height=self._get_coords([x0, y0, x1, y1], page_height)
        if height > 50:
            return None
        # Извлекаем слова
        words = self._extract_words_from_line(text_line, page_height)
        
        return {
            "segment": {
                "x_top_left": math.ceil(x_top_left),
                "y_top_left": math.ceil(y_top_left),
                "width": math.ceil(width),
                "height": math.ceil(height)
            },
            "text": text_line.get_text().strip(),
            "words": words
        }
    
    def _extract_words_from_line(self, text_line: LTTextLine, page_height: float) -> List[Dict]:
        """Извлечение слов из строки"""
        words = []
        current_word_chars = []
        current_word_bbox = None
        font_info = {}
        
        for child in text_line:
            if isinstance(child, LTChar):
                char_text = child.get_text()
                char_bbox = child.bbox
                # TODO: Сейчас по первой букве По первой букве!!!!
                fontname = child.fontname
                fontsize = child.size
                is_normal = child.upright
                
                if char_text.strip() and not char_text.isspace():
                    if not current_word_chars:
                        current_word_bbox = list(char_bbox)
                        font_info = {
                            "fontname": fontname, "fontsize": fontsize, "is_normal": is_normal
                        }
                    else:
                        current_word_bbox[0] = min(current_word_bbox[0], char_bbox[0])
                        current_word_bbox[1] = min(current_word_bbox[1], char_bbox[1])
                        current_word_bbox[2] = max(current_word_bbox[2], char_bbox[2])
                        current_word_bbox[3] = max(current_word_bbox[3], char_bbox[3])
                    
                    current_word_chars.append(char_text)
                else:
                    if current_word_chars:
                        word_info = self._create_word_info(
                            current_word_chars, current_word_bbox, page_height, font_info
                        )
                        words.append(word_info)
                        current_word_chars = []
                        font_info = {}
                        current_word_bbox = None
        
        if current_word_chars:
            word_info = self._create_word_info(
                current_word_chars, current_word_bbox, page_height, font_info
            )
            words.append(word_info)
        
        words = [word for word in words if self.__is_correct_segment(word['segment'])]
        return words
    
    def __is_correct_segment(self, segment):
        return segment['width'] > 0 and segment['height'] > 0

    def _process_image(self, image, page_height: float, page_w: int = None, page_h: int = None) -> Dict:
        """Обработка изображения/фигуры/кривой"""
        try:
            x_top_left, x_bottom_right, width, y_top_left, y_bottom_right, height = self._get_coords(image.bbox, page_height)

            if page_w is not None and page_h is not None:
                x_top_left = max(0, x_top_left)
                y_top_left = max(0, y_top_left)
                x_bottom_right = min(page_w, x_bottom_right)
                y_bottom_right = min(page_h, y_bottom_right)
                width = x_bottom_right - x_top_left
                height = y_bottom_right - y_top_left

            if not isinstance(image, LTImage):
                if width < 2:
                    width = 2
                if height < 2:
                    height = 2

            if width <= 0 or height <= 0:
                return None
            if isinstance(image, LTImage) and (width < 5 or height < 5):
                return None

            image_info = {
                "segment": {
                    "x_top_left": math.ceil(x_top_left),
                    "y_top_left": math.ceil(y_top_left),
                    "width": math.ceil(width),
                    "height": math.ceil(height),
                },
                "text": " "
            }

            if hasattr(image, 'name'):
                image_info['image_name'] = getattr(image, 'name', '')
            return image_info

        except Exception as e:
            print(f"Ошибка при обработке изображения: {e}")
            return None
    
    def _create_word_info(self, chars: List[str], bbox: List[float], page_height: float, font_info: Dict) -> Dict:
        """Создание информации о слове"""
        word_text = ''.join(chars)
        x_top_left, x_bottom_right, width, y_top_left, y_bottom_right, height=self._get_coords(bbox, page_height)
        
        word_segment = {
            "x_top_left": math.ceil(x_top_left),
            "y_top_left": math.ceil(y_top_left),
            "width": math.ceil(width),
            "height": math.ceil(height)
        }
        
        return {
            "segment": word_segment,
            "text": word_text,
            "font": font_info
        }



class MinerPDFModel(BasePDFasJsonModel):
    """Класс-аналог вашего PrecisionPDFModel, но использующий pdfminer"""
    def __init__(self, conf=None) -> None:
        if conf is None:
            conf = {}
        # Инициализируем парсер
        laparams = LAParams(
            line_margin=0.5,
            word_margin=0.1,
            char_margin=2.0,
            boxes_flow=0.5
        )
        conf['extractor'] = PDFStructureExtractor(laparams)
        super().__init__(conf)

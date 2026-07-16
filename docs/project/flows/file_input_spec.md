# Спецификация: модуль file_input (входная обработка документов)

**Версия:** 1.0  
**Дата:** 2026-07-16  
**Статус:** Актуальный  
**Модуль:** `src/pagerlib/file_input/`  
**Назначение:** загрузка неструктурированных документов (PDF, изображения), их парсинг и преобразование в унифицированное внутреннее представление `PageRDF`.

---

## 1. API модуля file_input

### 1.1 Класс `FileInput` (`file_input.py`)

Точка входа для загрузки документов. Реализует паттерн callable-объекта: экземпляр класса вызывается как функция, принимая путь к файлу и возвращая `PageRDF`.

```python
class FileInput:
    def __init__(self, *args)
    def __call__(self, path: Path | str) -> PageRDF
    def pdf_reader(self, path) -> PageRDF
    def image_reader(self, path) -> PageRDF
```

#### Конструктор `__init__(*args)`

Принимает keyword-аргументы через позиционный `*args` (tuple ключей-строк). Поддерживаемые ключи:

| Ключ | Тип | По умолчанию | Назначение |
|------|-----|-------------|------------|
| `"image_method"` | `str` | `"tesseract"` | Метод чтения изображений |
| `"pdf_method"` | `str` | `"miner"` | Метод чтения PDF |
| `"use_image_extractor"` | `bool` | `False` | (планируется) авто-запуск `Images2RegionsExtractor` после загрузки |
| `"image_extractor_conf"` | `dict` | `None` | (планируется) конфигурация для `Images2RegionsExtractor` |

Текущая реализация обрабатывает только `"image_method"` и `"pdf_method"`. Параметры `"use_image_extractor"` и `"image_extractor_conf"` зарезервированы для будущей интеграции с `Images2RegionsExtractor` (см. `docs/project/specs/image_extractor_spec.md`).

#### `__call__(self, path) -> PageRDF`

Роутинг по расширению файла:

1. `Path(path).is_file()` → если файл не существует: `FileNotFoundError`
2. Определение `path.suffix.lower()`:
   - `.pdf` → `self.pdf_reader(path)`
   - `.jpg`, `.jpeg`, `.png` → `self.image_reader(path)`
   - Иное расширение → **нет возврата** (неявное `None` — требуется доработка до `ValueError`)

#### `pdf_reader(self, path) -> PageRDF`

Делегирует вызов в `read_pdf(self.pdf_method, path)`.

#### `image_reader(self, path) -> PageRDF`

Делегирует вызов в `read_image(self.image_method, path)`.

---

### 1.2 Функция `read_image` (`tesseract/image_read.py`)

```python
def read_image(method: str, path: str) -> PageRDF
```

**Алгоритм:**

1. **Проверка Tesseract**: `shutil.which("tesseract")` — если `None`, выбрасывается `Exception("Tesseract is not installed")` (рекомендуется заменить на `RuntimeError`).
2. **Чтение изображения**: `Image.read_img(path)` → `np.ndarray` (BGR → RGB через `cv2.imdecode`).
3. **Создание Image-элемента**: `Image(data={"array": array, "path": path})`.
4. **OCR**: `Image2Words().get_region(image)` → `Region` (содержит `Row[Word]`).
5. **Сборка страницы**: `Page(children=[image, text_region])`.
6. **Упаковка**: `PageRDF(data={"pages": [page]})`.

**Примечание:** в отличие от `read_pdf`, здесь `path` не записывается в `prdf.data["path"]`.

---

### 1.3 Класс `Image2Words` (`tesseract/image2words.py`)

```python
class Image2Words:
    def __init__(self, conf: dict = None)
    def get_region(self, image: Image) -> Region
    def extract_from_img(self, img: np.ndarray) -> list[dict]
    def size_filter(self, row_list: list) -> list
```

#### Конфигурация Tesseract (`conf`)

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `lang` | `str` | `"eng+rus"` | Языки распознавания |
| `psm` | `int` | `4` | Page Segmentation Mode (один столбец переменного размера) |
| `oem` | `int` | `3` | OCR Engine Mode (LSTM + Legacy) |
| `k` | `int` | `1` | Множитель разрешения (resize factor) |
| `onetone_delete` | `bool` | `False` | Удаление однотонных блоков (фильтр по дисперсии < 20) |

Если `conf` передан, обновляются только ключи, присутствующие в словаре по умолчанию.

#### `get_region(self, image: Image) -> Region`

1. Вызывает `self.extract_from_img(image.img)` (использует свойство `.img`, которое извлекает `np.ndarray` из `data["array"]`).
2. Разделяет результат на строки с непустыми словами (`rows`) и пустые (`others`).
3. Возвращает `Region(children=rows)` — каждая строка становится `Row`.

#### `extract_from_img(self, img: np.ndarray) -> list[dict]`

1. **Resize**: `cv2.resize(img, dim)` с фактором `k`, интерполяция `INTER_AREA`.
2. **Tesseract**: `pytesseract.image_to_data()` с `output_type=Dict`:
   - `level=4` → строки (начало новой строки)
   - `level=5` → слова (добавляются в текущую строку)
3. **Обратное масштабирование координат**: деление `x0, y0, w, h` на `k` с округлением.
4. **Фильтр `onetone_delete`**: если включён, строки с дисперсией пикселей `< 20` пропускаются.
5. **Фильтр размера** (`size_filter`): строки с `width < 2` или `height < 2` удаляются.

**Формат возвращаемого списка:**

```python
[
    {
        "words": [
            {
                "text": "Hello",
                "segment": {
                    "x_top_left": int,  # x-координата левого верхнего угла (пиксели)
                    "y_top_left": int,  # y-координата левого верхнего угла (пиксели)
                    "width": int,
                    "height": int
                }
            },
            ...
        ],
        "segment": {
            "x_top_left": int,
            "y_top_left": int,
            "width": int,
            "height": int
        }
    },
    ...
]
```

**Важно:** в текущей реализации `confidence` (уверенность OCR) не извлекается. Это запланировано в `Images2RegionsExtractor` (см. спецификацию image_extractor).

---

### 1.4 Функция `read_pdf` (`pdf_as_json_model/pdf_read.py`)

```python
def read_pdf(method: str, path: str) -> PageRDF
```

Поддерживает два метода:

| Метод | Класс | Технология |
|-------|-------|-----------|
| `"miner"` | `MinerPDFModel` | pdfminer.six (Python) |
| `"precision"` | `PrecisionPDFModel` | Java JAR (precisionPDF) |

#### Алгоритм для `method == "miner"`

1. `MinerPDFModel().read_from_file(path)` — парсинг PDF через `PDFStructureExtractor`.
2. `miner.extract()` — применение `page_model` (если задан).
3. `miner.to_dict()` → `pdf_json` со структурой `{document, pages: [{number, width, height, rows, images}]}`.
4. Для каждой страницы:
   - **Image-элементы** из `page_json["images"]` — создаются через `Image(ImageSegment(...), {})` **без pixel array** (только координаты).
   - **Регионы текста** из `page_json["rows"]` — создаются через `Region.get_none().from_dict({"rows": ...})`, что строит `Row[Word]` с координатами, текстом и шрифтом.
   - Если `rows` пусты → страница пропускается (не добавляется в `pages`).
   - `Page(segment=ImageSegment(0, 0, w, h), children=regions)`.
5. `PageRDF(data={"pages": pages, "path": pdf_json["document"]})`.

**Особенность:** в отличие от `read_image`, здесь Image-элементы **не содержат pixel array** — только метаинформацию о положении на странице.

#### Алгоритм для `method == "precision"`

1. `PrecisionPDFModel().read_from_file(path)` → запуск Java-процесса `precisionPDF.jar`.
2. `precision.extract()` → применение page_model.
3. Возврат `precision.to_dict()` — **сырой словарь**, не `PageRDF`. Это расхождение с сигнатурой для `"miner"`.

---

## 2. PDF-модели

### 2.1 Иерархия классов

```
BaseExtractor (ABC)                    BasePDFasJsonModel (ABC)
    │                                       │
    ├── PDFStructureExtractor               ├── MinerPDFModel
    │   (miner_pdf_model)                   │   (miner_pdf_model)
    │                                       │
    └── JarExtractor                        └── PrecisionPDFModel
        (precision_pdf_model)                   (precision_pdf_model)
```

### 2.2 `BasePDFasJsonModel` (`base_pdf_as_json_model.py`)

Абстрактный базовый класс для PDF-моделей.

| Поле | Тип | Описание |
|------|-----|----------|
| `pdf_json` | `Dict` | Распарсенная JSON-структура документа |
| `count_page` | `int` | Количество страниц |
| `page_model` | `object` или `None` | Модель постобработки страницы |
| `extractor` | `BaseExtractor` | Экстрактор для парсинга файла |
| `path` | `str` | Путь к исходному файлу (устанавливается в `read_from_file`) |

**Методы:**

| Метод | Описание |
|-------|----------|
| `read_from_file(path)` | Устанавливает `pdf_json` через `self.extractor.extract_from_path(path)`, обновляет `count_page` |
| `extract()` | Применяет `page_model` к каждой странице (если задан) |
| `to_dict()` | Сериализация — возвращает `self.pdf_json` (базовая реализация, не абстрактная) |
| `from_dict(d)` | Загружает `pdf_json` из словаря |
| `clean_model()` | Сбрасывает `pdf_json = {}` и `count_page = None` |

### 2.3 `BaseExtractor` (абстрактный)

```python
class BaseExtractor(ABC):
    @abstractmethod
    def extract_from_path(self, path: str) -> Dict:
        """Парсит файл и возвращает JSON-структуру документа."""
```

### 2.4 `MinerPDFModel` (`miner_pdf_model/model.py`)

Конкретная реализация `BasePDFasJsonModel` на базе pdfminer.six.

```python
class MinerPDFModel(BasePDFasJsonModel):
    def __init__(self, conf=None)
```

**Конструктор:**
- Создаёт `LAParams(line_margin=0.5, word_margin=0.1, char_margin=2.0, boxes_flow=0.5)`.
- Извлекает из `conf` отладочные флаги: `debug_curves`, `debug_timing`.
- Создаёт `PDFStructureExtractor(laparams, ...)` и передаёт его как `extractor`.
- Вызывает `super().__init__(conf)`.

### 2.5 `PrecisionPDFModel` (`precision_pdf_model/precision_pdf_model.py`)

Конкретная реализация `BasePDFasJsonModel`, использующая внешний Java-процесс.

```python
class PrecisionPDFModel(BasePDFasJsonModel):
    def __init__(self, conf=None)
```

Создаёт `JarExtractor` с путём к JAR-файлу (`conf["jar_path"]` или `get_model_path("precisionPDF.jar")`).

#### `JarExtractor.extract_from_path(path)`

Запускает `java -jar precisionPDF.jar -i <path>`, парсит stdout как JSON. При ошибке парсинга возвращает пустой `dict()`.

---

## 3. PDFStructureExtractor — основной парсер PDF

`PDFStructureExtractor` (`miner_pdf_model/extractor.py`) — реализация `BaseExtractor` (через duck-typing, без формального наследования), выполняющая полный разбор PDF.

### 3.1 Конструктор

```python
class PDFStructureExtractor:
    BASE_DPI = 72

    def __init__(self, laparams=None, debug_curves=False, debug_timing=False):
        self.laparams = laparams or LAParams(...)
        self.text = TextExtractor()
        self.visual = VisualExtractor(debug_curves=debug_curves)
```

### 3.2 `extract_from_path(pdf_path) -> Dict`

**Основной алгоритм:**

1. Открывает PDF через `PDFParser` / `PDFDocument`.
2. Создаёт `PDFResourceManager` и `_FastPDFPageAggregator` (кастомный агрегатор, наследующий `PDFPageAggregator`).
3. Итерирует `PDFPage.create_pages(document)`:
   - `interpreter.process_page(page)` — рендеринг страницы.
   - Извлекает `path_bboxes` и `figure_path_bboxes` из агрегатора.
   - Вызывает `_process_page()`.
4. Возвращает `{"document": pdf_path, "pages": [...]}`.

### 3.3 `_process_page(page_layout, page_number, path_bboxes, figure_path_bboxes) -> Dict`

Обработка одной страницы:

1. **Сбор элементов**: `_collect_elements(page_layout, elements, stop_types=LTFigure)` — рекурсивный обход дерева layout, остановка на `LTFigure` (не заходит внутрь фигур).
2. **Построение skip_ids**: `_build_figure_skip_ids(elements)` — элементы внутри `LTFigure` (изображения и кривые) помечаются для пропуска на верхнем уровне (они будут обработаны внутри фигуры отдельно).
3. **Классификация**: `_classify_visual_elements(elements, skip_ids)` → три списка:
   - `text_lines: list[LTTextLine]`
   - `page_chars: list[LTChar]` (символы вне текстовых строк)
   - `visuals: list[LTImage | LTCurve | _PreMergedBox]`
4. **Извлечение текстовых строк**: `_extract_text_rows()`:
   - Если `text_lines` пуст, но есть `page_chars` → `char_lines.chars_to_text_lines(page_chars)` — эвристическая сборка строк из отдельных символов.
   - Для каждой `LTTextLine` → `TextExtractor.process_text_line(text_line, page_height)`.
   - Фильтрация: валидный `segment`, непустые `words`.
   - `TextExtractor.merge_vertical_rows(rows)` — слияние вертикальных строк.
5. **Добавление path-визуальных элементов**: `_add_path_visuals()` — группирует `path_bboxes` через морфологическое слияние, добавляет как `_PreMergedBox` в `visuals`.
6. **Извлечение изображений**: `_extract_image_infos(visuals, ...)` → `VisualExtractor.merge_overlapping_images()` + `process_image()` → список `{segment, text: " "}`.
7. **Сортировка**: строки и изображения сортируются по `y_top_left`.
8. **Возврат**: `{number, width, height, rows, images}`.

### 3.4 `_FastPDFPageAggregator` (`aggregator.py`)

Кастомный агрегатор pdfminer, расширяющий `PDFPageAggregator`:

- Записывает bounding box каждого отрисованного path (`paint_path`).
- Отслеживает вложенность `begin_figure` / `end_figure` для группировки path-bbox по Form XObject.
- Методы `get_path_bboxes()` / `get_figure_path_bboxes()` возвращают накопленные bbox.
- `clear_path_bboxes()` — очистка между страницами.

Также определён `_TextOnlyAggregator` (наследует `PDFPageAggregator`) — подавляет `paint_path` для быстрого извлечения только текста (используется в фазе 1 быстрого парсинга).

### 3.5 `fast_path_parser.py`

Легковесный байтовый сканер для извлечения path-bbox напрямую из бинарных content streams PDF (без полного парсинга pdfminer). Публичная функция:

```python
def extract_path_bboxes_from_bytes(content_bytes: bytes) -> List[Tuple[float, ...]]
```

Отслеживает CTM (Current Transformation Matrix), обрабатывает операторы `m`, `l`, `c`, `v`, `y`, `re`, `cm`, `q`, `Q`, фиксирует bbox для каждого path. Возвращает список `(x0, y0, x1, y1)` в координатах PDF (points).

---

## 4. TextExtractor — извлечение текста

`TextExtractor` (`miner_pdf_model/text_extractor.py`) преобразует объекты `LTTextLine` pdfminer в структурированные словари.

### 4.1 Конфигурационные константы

| Константа | Значение | Назначение |
|-----------|----------|------------|
| `MAX_TEXT_LINE_HEIGHT` | 50 | Максимальная высота текстовой строки (пиксели) |
| `VERTICAL_X_GAP` | 3 | Допуск по X при группировке вертикальных кандидатов |
| `VERTICAL_MIN_RUN` | 3 | Минимальная длина вертикальной цепочки |
| `VERTICAL_GAP_MULT` | 4 | Множитель медианного gap для вертикального слияния |
| `VERTICAL_GAP_MIN` | 6 | Минимальный gap для вертикального слияния |
| `VERTICAL_GAP_HEIGHT_FACTOR` | 0.5 | Фактор высоты символа для расчёта max_gap |
| `VERTICAL_GAP_HEIGHT_MAX` | 1.5 | Максимальный множитель высоты символа |

### 4.2 `process_text_line(text_line, page_height) -> Dict | None`

1. Пропускает пустые строки (`.get_text().strip() == ""`).
2. Конвертирует bbox `(x0, y0, x1, y1)` из PDF-координат в пиксельные через `coordinate_utils.get_coords()`.
3. Отбрасывает строки с `height > MAX_TEXT_LINE_HEIGHT`.
4. Извлекает слова через `_extract_words()`.
5. Возвращает:

```python
{
    "segment": {"x_top_left": int, "y_top_left": int, "width": int, "height": int},
    "text": str,           # полный текст строки
    "words": [
        {
            "segment": {"x_top_left": int, "y_top_left": int, "width": int, "height": int},
            "text": str,
            "font": {
                "fontname": str,
                "fontsize": float,     # размер в точках PDF
                "is_normal": bool,     # upright флаг из LTChar
            }
        },
        ...
    ]
}
```

### 4.3 `_extract_words(text_line, page_height) -> List[Dict]`

Группирует последовательные `LTChar` в слова:
- Непробельные символы накапливаются в текущее слово.
- Пробельный символ завершает текущее слово и начинает новое.
- Для каждого слова вычисляется охватывающий bbox и извлекается информация о шрифте первого символа.

**Фильтрация:** слова с некорректным segment (`width <= 0` или `height <= 0`) отбрасываются.

### 4.4 `merge_vertical_rows(rows) -> List[Dict]`

Обнаружение и слияние вертикальных строк (например, в японском/китайском тексте):

1. **Поиск кандидатов**: строки из одного слова длиной 1 символ.
2. **Группировка по X**: кандидаты с `|x0 - x0'| <= VERTICAL_X_GAP` объединяются.
3. **Расчёт gap**: медианный вертикальный зазор в группе.
4. **Вычисление max_gap**: `min(max(med_gap * 4, char_height * 0.5, 6), char_height * 1.5)`.
5. **Построение цепочек** (runs): последовательные кандидаты с gap `<= max_gap`.
6. **Слияние цепочек**: для каждой цепочки длиной `>= VERTICAL_MIN_RUN` создаётся объединённая строка с охватывающим bbox и конкатенированным текстом.

### 4.5 `is_correct_segment(segment) -> bool`

Статический метод: `segment['width'] > 0 and segment['height'] > 0`.

---

## 5. VisualExtractor — извлечение изображений

`VisualExtractor` (`miner_pdf_model/visual_extractor.py`) обрабатывает визуальные элементы PDF: изображения, кривые, path-bbox.

### 5.1 Конфигурационные константы

| Константа | Значение | Назначение |
|-----------|----------|------------|
| `MORPH_SCALE` | 2 | Масштаб для морфологических операций |
| `MORPH_DILATE_RADIUS` | 10 | Радиус дилатации |
| `MORPH_MIN_AREA` | 500 | Минимальная площадь компонента связности |
| `DECO_LINE_ASPECT_RATIO` | 15.0 | Максимальный aspect ratio декоративной линии |
| `DECO_LINE_PAGE_SPAN` | 0.5 | Максимальный относительный размер bbox |
| `MERGE_OVERLAP_PAD` | 2 | Padding для проверки пересечений |
| `MIN_LTIMAGE_SIZE` | 5 | Минимальный размер для LTImage |
| `MIN_NON_IMAGE_SIZE` | 2 | Минимальный размер для не-LTImage элементов |

### 5.2 `merge_path_bboxes(bboxes, page_w, page_h) -> List`

Морфологическое слияние path-bbox:

1. Если `len(bboxes) <= 1` или `debug_curves` — возврат без изменений.
2. Создаётся бинарный canvas размера `(page_h * 2, page_w * 2)`.
3. Каждый bbox рисуется как белая область; bbox, занимающие `> 50%` страницы, игнорируются.
4. Морфологическое закрытие (`cv2.MORPH_CLOSE`, эллиптическое ядро).
5. Поиск connected components → фильтрация по `area >= MORPH_MIN_AREA`.
6. Результат: список `(x, y, x+w, y+h)` в пиксельных координатах.

### 5.3 `merge_overlapping_images(elements) -> List`

Union-find слияние пересекающихся визуальных элементов:

1. Для каждой пары проверяется пересечение bbox с padding `MERGE_OVERLAP_PAD`.
2. Пересекающиеся элементы объединяются в группы (union-find).
3. Группы из нескольких элементов сливаются в `_MergedElement` с охватывающим bbox.
4. Процесс повторяется итеративно до стабилизации.

**Типы элементов:** `LTImage`, `LTFigure`, `LTCurve`, `_MergedElement`, `_PreMergedBox`.

### 5.4 `extract_from_figure(figure) -> List`

Извлечение визуальных элементов из `LTFigure`:
1. Рекурсивный сбор всех дочерних элементов.
2. Разделение на `LTImage`, вложенные `LTFigure` и `LTCurve`.
3. Кривые сливаются в один `_MergedElement` (если `debug_curves=False`).
4. Возвращается список из объединённых кривых + изображений + вложенных фигур.

### 5.5 `process_image(image, page_height, page_w, page_h) -> Dict | None`

Конвертация визуального элемента в словарь-инфо:

1. Конвертация координат `image.bbox` через `coord.get_coords()`.
2. Clamping к границам страницы `[0, page_w] × [0, page_h]`.
3. Применение минимальных размеров: `MIN_LTIMAGE_SIZE=5` для изображений, `MIN_NON_IMAGE_SIZE=2` для остальных.
4. Возврат:

```python
{
    "segment": {"x_top_left": int, "y_top_left": int, "width": int, "height": int},
    "text": " ",                          # пробел-заглушка
    "image_name": str | None,             # если есть атрибут name
}
```

---

## 6. Вспомогательные модули

### 6.1 `coordinate_utils.py`

```python
def pdf_to_pixel(x, y, page_height_points, dpi=None) -> (int, int):
    """Конвертация PDF-координат (points, нижний левый угол) в пиксельные
    (верхний левый угол). Y переворачивается: y_px = (page_h - y) * dpi / 72."""

def get_coords(bbox, page_height) -> (x_tl, x_br, w, y_tl, y_br, h):
    """Конвертация bbox (x0, y0, x1, y1) из PDF-координат в 6 пиксельных значений."""
```

**Ключевое преобразование:**
- `bbox = (x_ll, y_ll, x_ur, y_ur)` — PDF, нижний левый угол.
- `x_tl = x_ll * 72/72` (без изменений, DPI по умолчанию 72).
- `y_tl = (page_height - y_ur) * 72/72` — flip Y.
- Все результаты целочисленные (`int`).

### 6.2 `char_lines.py`

Эвристическая сборка `LTTextLine` из разрозненных `LTChar` (когда pdfminer не смог сгруппировать символы в строки).

```python
def chars_to_text_lines(chars: List[LTChar]) -> List[_Line]
```

**Алгоритм:**
1. Разделение на горизонтальные (`is_vertical_char = False`) и вертикальные символы.
2. Группировка по оси Y (горизонтальные) или X (вертикальные) с допуском `CHAR_LINE_ALIGN=2`.
3. Разбиение групп с большими горизонтальными/вертикальными зазорами: `gap > max(median_gap * 3, 15)`.
4. Оборачивание в duck-typed `_Line` с методами `get_text()`, `__iter__()`, атрибутами `x0, y0, x1, y1`.

### 6.3 `merged_element.py`

Вспомогательные классы-обёртки:

- `_MergedElement(bbox, name=None)` — результат окончательного слияния (используется в `merge_overlapping_images`).
- `_PreMergedBox(bbox, name=None)` — результат предварительного слияния path-bbox (подвергается дальнейшему `merge_overlapping_images` с padding).

---

## 7. Диаграммы потоков данных

### 7.1 Поток 1: обработка PDF через MinerPDFModel

```
document.pdf
  │
  ▼
FileInput.__call__(path)
  │  (path.suffix == ".pdf")
  ▼
FileInput.pdf_reader(path)
  │
  ▼
read_pdf("miner", path)
  │
  ▼
MinerPDFModel.read_from_file(path)
  │  └─ PDFStructureExtractor.extract_from_path(path)
  │      │
  │      ├─ PDFParser(PDFDocument(fp))
  │      ├─ _FastPDFPageAggregator + PDFPageInterpreter
  │      │
  │      └─ Для каждой страницы → _process_page():
  │          │
  │          ├─ _collect_elements(page_layout, ..., stop_types=LTFigure)
  │          │   └─ Рекурсивный обход дерева layout
  │          │
  │          ├─ _build_figure_skip_ids(elements)
  │          │   └─ Поиск LTImage/LTCurve внутри LTFigure → skip
  │          │
  │          ├─ _classify_visual_elements(elements, skip_ids)
  │          │   ├─ LTTextLine → text_lines
  │          │   ├─ LTChar (вне строк) → page_chars
  │          │   ├─ LTImage → visuals
  │          │   ├─ LTFigure → VisualExtractor.extract_from_figure()
  │          │   └─ LTCurve → visuals
  │          │
  │          ├─ _extract_text_rows(text_lines, page_chars, page_height)
  │          │   ├─ chars_to_text_lines(page_chars) — если нет text_lines
  │          │   ├─ TextExtractor.process_text_line() для каждой
  │          │   │   ├─ coord.get_coords(bbox, page_height) → пиксельные x_tl, y_tl, w, h
  │          │   │   ├─ _extract_words() → [{segment, text, font}]
  │          │   │   └─ Фильтр: is_correct_segment + непустые words
  │          │   └─ TextExtractor.merge_vertical_rows()
  │          │       ├─ _find_vertical_candidates() — однобуквенные строки
  │          │       ├─ _group_by_x_position() — группировка по X
  │          │       ├─ _calc_vertical_gap() — медианный gap
  │          │       └─ _build_vertical_runs() + _merge_runs_to_rows()
  │          │
  │          ├─ _add_path_visuals(visuals, path_bboxes, figure_path_bboxes)
  │          │   └─ VisualExtractor.merge_path_bboxes()
  │          │       └─ Морфологическое слияние (MORPH_CLOSE + connected components)
  │          │
  │          └─ _extract_image_infos(visuals, page_height, page_w, page_h)
  │              ├─ VisualExtractor.merge_overlapping_images()
  │              │   └─ Union-find группировка пересекающихся bbox
  │              └─ VisualExtractor.process_image() для каждого
  │                  └─ coord.get_coords() + clamp + min size → {segment, text: " "}
  │
  ▼
JSON-структура:
  {
    "document": "/path/to/document.pdf",
    "pages": [
      {
        "number": 0,
        "width": 595,   # page_w в пикселях
        "height": 842,  # page_h в пикселях
        "rows": [
          {
            "segment": {"x_top_left", "y_top_left", "width", "height"},
            "text": "Hello world",
            "words": [
              {
                "segment": {"x_top_left", "y_top_left", "width", "height"},
                "text": "Hello",
                "font": {"fontname": "...", "fontsize": 12.0, "is_normal": true}
              },
              ...
            ]
          },
          ...
        ],
        "images": [
          {"segment": {"x_top_left", "y_top_left", "width", "height"}, "text": " "},
          ...
        ]
      },
      ...
    ]
  }
  │
  ▼
MinerPDFModel.extract()
  │  └─ Применение page_model (если задан)
  │
  ▼
miner.to_dict() → pdf_json
  │
  ▼
Преобразование json → PageRDF (в read_pdf):
  │
  ├─ Для каждой страницы:
  │   ├─ Image-элементы из images: Image(ImageSegment(segment), data={})
  │   │   └─ БЕЗ pixel array — только координаты
  │   ├─ Region из rows: Region.get_none().from_dict({"rows": rows})
  │   │   └─ Восстановление Row → Word через метакласс ElementMeta
  │   └─ Page(segment=ImageSegment(0,0,w,h), children=[Image..., Region...])
  │
  └─ PageRDF(data={"pages": List[Page], "path": str})
```

### 7.2 Поток 2: обработка изображения через Tesseract

```
photo.png
  │
  ▼
FileInput.__call__(path)
  │  (path.suffix in {".jpg", ".jpeg", ".png"})
  ▼
FileInput.image_reader(path)
  │
  ▼
read_image("tesseract", path)
  │
  ├─ shutil.which("tesseract") → проверка наличия
  │   └─ None → Exception("Tesseract is not installed")
  │
  ├─ Image.read_img(path)
  │   └─ cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)
  │   └─ cv2.cvtColor(BGR → RGB)
  │   └─ Возвращает np.ndarray (H, W, 3) uint8
  │
  ├─ Image(data={"array": array, "path": path})
  │
  ├─ Image2Words(conf).get_region(image)
  │   │
  │   └─ extract_from_img(image.img)
  │       │
  │       ├─ cv2.resize(img, (k*W, k*H), INTER_AREA)
  │       │
  │       ├─ pytesseract.image_to_data(
  │       │       config="-l eng+rus --psm 4 --oem 3",
  │       │       output_type=Dict)
  │       │   └─ Возвращает словарь с ключами:
  │       │       level[], left[], top[], width[], height[], text[], conf[]
  │       │
  │       ├─ Итерация по level:
  │       │   ├─ level=4 (строка): создаётся новый блок строки
  │       │   │   ├─ Координаты /= k (обратное масштабирование)
  │       │   │   └─ Если onetone_delete: проверка np.var < 20 → skip
  │       │   │
  │       │   └─ level=5 (слово): добавляется в words текущей строки
  │       │       ├─ text из tesseract
  │       │       └─ segment с координатами /= k
  │       │
  │       └─ size_filter(): удаление строк с width<2 или height<2
  │
  ├─ Region(children=rows)
  │   └─ Каждый row → Row(children=[Word(segment, data={"text": ...})])
  │
  ├─ Page(children=[image, text_region])
  │
  └─ PageRDF(data={"pages": [Page]})
```

### 7.3 Поток 3: роутинг в FileInput

```
FileInput.__call__(path)
  │
  ├─ Path(path).is_file()
  │   └─ False → FileNotFoundError(f"{path} is not a file")
  │
  ├─ path.suffix.lower()
  │
  ├─ suffix == ".pdf"
  │   └─ pdf_reader(path)
  │       └─ read_pdf(self.pdf_method, path) → PageRDF
  │
  ├─ suffix in {".jpg", ".jpeg", ".png"}
  │   └─ image_reader(path)
  │       └─ read_image(self.image_method, path) → PageRDF
  │
  └─ Иное расширение
      └─ Неявный возврат None (БАГ: должен быть ValueError)
```

---

## 8. Координатные системы

### 8.1 Обзор

| Источник | Начало координат | Единицы | Конвертация |
|----------|-----------------|---------|-------------|
| PDF (pdfminer) | Нижний левый угол | Точки (1/72 дюйма) | `coord.get_coords()` |
| Tesseract (изображения) | Верхний левый угол | Пиксели | Прямые (с коррекцией `k`) |
| PageRDF (dtypes) | Верхний левый угол | Пиксели, целочисленные | Целевой формат |

### 8.2 `coordinate_utils.get_coords(bbox, page_height)`

```
Вход:  bbox = (x_ll, y_ll, x_ur, y_ur)   — PDF-координаты
Выход: x_tl, x_br, w, y_tl, y_br, h      — пиксельные координаты

x_tl = min(pdf_to_pixel(x_ll, y_ur, ph), pdf_to_pixel(x_ur, y_ll, ph))
y_tl = min(pdf_to_pixel(x_ll, y_ur, ph), pdf_to_pixel(x_ur, y_ll, ph))  # Y-координата
x_br = max(...)
y_br = max(...)
w = x_br - x_tl
h = y_br - y_tl
```

### 8.3 `pdf_to_pixel(x, y, page_height_points, dpi=72)`

```
x_px = x * dpi / 72.0
y_px = (page_height_points - y) * dpi / 72.0   # flip Y
→ (int(x_px), int(y_px))
```

### 8.4 Размеры страниц PDF

В `_process_page()`:
```python
page_w = math.ceil(page_layout.width  * 72 / 72)  # = ceil(width)
page_h = math.ceil(page_layout.height * 72 / 72)  # = ceil(height)
```

При DPI = 72: 1 точка PDF = 1 пиксель. Страница A4 (595×842 точек) → 595×842 пикселей.

### 8.5 Размеры в Tesseract

Координаты из `pytesseract.image_to_data()` возвращаются в пикселях относительно увеличенного изображения (`k * W × k * H`). Обратное масштабирование:

```python
x0 = round(left / k)
y0 = round(top / k)
w  = round(width / k)
h  = round(height / k)
```

---

## 9. Обработка ошибок

| Ситуация | Текущее поведение | Рекомендуемое поведение |
|----------|-------------------|------------------------|
| Файл не существует | `FileNotFoundError(f"{path} is not a file")` | Оставить как есть |
| Tesseract не установлен | `Exception("Tesseract is not installed")` | `RuntimeError("Tesseract is not installed. Install: apt install tesseract-ocr")` |
| PDF повреждён / не читается | Исключение из pdfminer.six (пробрасывается) | Оставить как есть |
| Неподдерживаемое расширение | Неявный возврат `None` (нет `return`) | `ValueError(f"Unsupported file extension: {suffix}")` |
| Изображение не читается (cv2) | Исключение из cv2.imdecode (пробрасывается) | Оставить как есть |
| PDF без страниц | `PageRDF(data={"pages": [], "path": ...})` — валидный результат | Оставить как есть |
| Строка Tesseract пустая (нет слов) | Кладётся в `others`, игнорируется | Оставить как есть |
| Ошибка парсинга precision JAR JSON | Возвращается `dict()`, ошибка печатается в stdout | Требует улучшения: логгирование вместо print |
| `Image.read_img()` не может прочитать файл | Исключение из cv2 | Оставить как есть |

---

## 10. Формат сегмента (segment)

Все координатные словари в модуле используют единый формат:

```python
{
    "x_top_left": int,  # x-координата левого верхнего угла (пиксели)
    "y_top_left": int,  # y-координата левого верхнего угла (пиксели)
    "width": int,       # ширина (пиксели)
    "height": int       # высота (пиксели)
}
```

Этот формат используется в:
- `ImageSegment` (из `pagerlib.dtypes`)
- Строках и словах в `TextExtractor`
- Изображениях в `VisualExtractor`
- Результатах `Image2Words.extract_from_img()`

---

## 11. Структура модуля

```
src/pagerlib/file_input/
├── __init__.py                      # Экспорт FileInput
├── file_input.py                    # Класс FileInput (точка входа)
│
├── tesseract/
│   ├── __init__.py                  # Экспорт read_image
│   ├── image_read.py                # read_image() — загрузка изображений + OCR
│   └── image2words.py               # Image2Words — Tesseract OCR engine
│
└── pdf_as_json_model/
    ├── __init__.py                  # Экспорт: read_pdf, BasePDFasJsonModel
    ├── base_pdf_as_json_model.py    # BasePDFasJsonModel, BaseExtractor (ABC)
    ├── pdf_read.py                  # read_pdf() — роутинг PDF-методов
    │
    ├── miner_pdf_model/
    │   ├── __init__.py
    │   ├── miner_pdf_model.py       # Реэкспорт MinerPDFModel, PDFStructureExtractor
    │   ├── model.py                 # MinerPDFModel (конкретный класс)
    │   ├── extractor.py             # PDFStructureExtractor (основной парсер)
    │   ├── aggregator.py            # _FastPDFPageAggregator, _TextOnlyAggregator
    │   ├── text_extractor.py        # TextExtractor — извлечение текста из LTTextLine
    │   ├── visual_extractor.py      # VisualExtractor — извлечение изображений
    │   ├── coordinate_utils.py      # pdf_to_pixel(), get_coords()
    │   ├── char_lines.py            # chars_to_text_lines() — сборка строк из LTChar
    │   ├── merged_element.py        # _MergedElement, _PreMergedBox
    │   └── fast_path_parser.py      # extract_path_bboxes_from_bytes()
    │
    └── precision_pdf_model/
        ├── __init__.py
        ├── precision_pdf_model.py   # PrecisionPDFModel + JarExtractor
        ├── image_as_precision_pdf.py # (закомментирован) ImageAsPrecisionPDFModel
        └── exaption_pdf.py          # Обработка исключений precision PDF
```

---

## 12. Связанные документы

| Документ | Путь |
|----------|------|
| Спецификация ImageExtractor | `docs/project/specs/image_extractor_spec.md` |
| API-спецификация | `docs/project/api/` |
| ADR (архитектурные решения) | `docs/project/adr/` |
| Модели данных | `docs/project/models/` |

# Спецификация типов данных PageRLib

> Версия: 1.0  
> Дата: 2026-07-16  
> Модуль: `src/pagerlib/dtypes/`

---

## 1. Иерархия типов (схема наследования)

```
ABC
├── ImageSegment                         (базовый bounding box)
├── PhysicalElement(ABC)                 (абстрактный физический элемент страницы)
│   ├── Page                             (дети: List[Region], ключ "regions")
│   ├── Region                           (дети: List[Row], ключ "rows")
│   ├── Row                              (дети: List[Word], ключ "words")
│   ├── Word                             (листовой элемент — текстовый токен)
│   └── Image                            (листовой элемент — изображение)
├── PageRDF                              (корневой контейнер документа)
├── Section                              (логический элемент — секция/заголовок)
├── Context                              (логический элемент — контекст внутри секции)
├── Font                                 (метаданные шрифта)
├── Node                                 (вершина графа для GNN)
├── NoneNode(Node)                       (нулевая вершина-заглушка)
├── Edge                                 (ребро графа)
├── RelatedGraph                         (связный подграф)
└── Graph                                (контейнер графа — DSU над RelatedGraph)

SegmentException(Exception)
├── PositionException                    (некорректные координаты)
└── TypeArgError                         (вещественные координаты вместо целых)
```

---

## 2. Детальное описание каждого типа

---

### 2.1. ImageSegment (ABC)

**Назначение:**  
Базовый класс для представления прямоугольного bounding box на странице. Определяет координатную систему, методы геометрических операций и визуализации. Наследует `ABC`, но не содержит абстрактных методов — это конкретный класс, используемый повсеместно.

**Файл:** `src/pagerlib/dtypes/image_segment.py`

#### Поля

| Поле | Тип | Назначение |
|------|-----|------------|
| `x_top_left` | `int` | X-координата верхнего левого угла |
| `y_top_left` | `int` | Y-координата верхнего левого угла |
| `x_bottom_right` | `int` | X-координата нижнего правого угла |
| `y_bottom_right` | `int` | Y-координата нижнего правого угла |
| `info` | `dict` | Словарь для хранения произвольных метаданных сегмента |

#### Свойства (property)

| Свойство | Тип | Описание |
|----------|-----|----------|
| `height` | `int` | `y_bottom_right - y_top_left` |
| `width` | `int` | `x_bottom_right - x_top_left` |

#### Методы

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `__init__` | `(x_top_left=None, y_top_left=None, x_bottom_right=None, y_bottom_right=None, dict_2p=None, dict_p_size=None)` | Создаёт сегмент из 4 координат, либо из словаря формата 2-точки, либо из словаря формата точка+размер |
| `_set_segment` | `(x_top_left: int, y_top_left: int, x_bottom_right: int, y_bottom_right: int)` | Устанавливает координаты с валидацией. Выбрасывает `PositionException` если x/y инвертированы, `TypeArgError` если координаты не `int` |
| `set_segment_2p` | `(dict_2point: Dict)` | Устанавливает координаты из словаря `{"x_top_left", "y_top_left", "x_bottom_right", "y_bottom_right"}` |
| `set_segment_p_size` | `(dict_2point: Dict)` | Устанавливает координаты из словаря `{"x_top_left", "y_top_left", "width", "height"}` |
| `set_segment_max_segments` | `(segments: List[ImageSegment])` | Устанавливает bounding box как минимальный охватывающий прямоугольник вокруг списка сегментов |
| `get_segment_2p` | `() -> Dict` | Возвращает словарь формата 2-точки |
| `get_segment_p_size` | `() -> Dict` | Возвращает словарь формата точка+размер |
| `get_segment_from_img` | `(img: np.ndarray, delta=0) -> np.ndarray` | Вырезает фрагмент изображения по координатам сегмента (с отступом `delta`) |
| `get_height` | `() -> int` | Возвращает высоту |
| `get_width` | `() -> int` | Возвращает ширину |
| `get_center` | `() -> Tuple[int, int]` | Возвращает координаты центра `(x_c, y_c)` (округлённые) |
| `is_intersection` | `(seg: ImageSegment) -> bool` | Проверяет пересечение с другим сегментом (по углам и центрам) |
| `add_segment` | `(seg: ImageSegment)` | Расширяет текущий сегмент до минимального охватывающего вместе с `seg` |
| `add_info` | `(key: str, val: np.ndarray)` | Добавляет значение в `self.info` |
| `get_info` | `(key) -> Any` | Извлекает значение из `self.info` |
| `get_min_dist` | `(seg: ImageSegment) -> float` | Минимальное расстояние между двумя сегментами (угол-к-углу) |
| `get_angle_center` | `(seg: ImageSegment) -> float` | Косинус угла между центрами сегментов (0 — вертикаль, 1 — горизонталь) |
| `resize` | `(k: float)` | Масштабирует координаты на коэффициент `k` (с округлением) |
| `copy` | `() -> ImageSegment` | Создаёт копию сегмента |
| `plot` | `(color="b", text="", text_size='medium', width=1)` | Рисует bounding box через matplotlib |

#### Способы конструирования

```python
# Способ 1: явные координаты
ImageSegment(x_top_left=10, y_top_left=20, x_bottom_right=100, y_bottom_right=50)

# Способ 2: словарь 2-точки
ImageSegment(dict_2p={"x_top_left": 10, "y_top_left": 20, "x_bottom_right": 100, "y_bottom_right": 50})

# Способ 3: словарь точка+размер
ImageSegment(dict_p_size={"x_top_left": 10, "y_top_left": 20, "width": 90, "height": 30})
```

#### Инварианты
- `x_top_left < x_bottom_right` и `y_top_left < y_bottom_right`
- Все координаты — строго `int` (float не допускается, вызывает `TypeArgError`)
- `height = y_bottom_right - y_top_left >= 1`
- `width = x_bottom_right - x_top_left >= 1`

#### Координатная система
- Начало координат: верхний левый угол страницы.
- Ось X: вправо, ось Y: вниз (стандартная экранная система).
- Все координаты в пикселях.

---

### 2.2. PhysicalElement (ABC)

**Назначение:**  
Абстрактный базовый класс для всех физических элементов страницы (Page, Region, Row, Word, Image). Реализует иерархическую модель parent–children, унифицированную сериализацию/десериализацию и автоматическое вычисление bounding box по детям.

**Файл:** `src/pagerlib/dtypes/physical_elements/base_physical_element.py`

#### Поля

| Поле | Тип | Назначение |
|------|-----|------------|
| `segment` | `ImageSegment` | Bounding box элемента. Вычисляется автоматически из children, если не передан явно |
| `children` | `List[PhysicalElement] \| None` | Дочерние элементы. `None` для листовых элементов |
| `data` | `Dict \| None` | Словарь с данными элемента (текст, метка, шрифт, вектор и т.д.) |
| `name_children` | `str \| None` | Ключ для сериализации children (напр. "regions", "rows", "words"). `None` для листовых |

#### Свойства (abstract)

| Свойство | Тип | Описание |
|----------|-----|----------|
| `text` | `str` | Текстовое содержимое элемента (рекурсивно агрегируется из детей) |

#### Методы

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `__init__` | `(segment=None, children=None, data=None, name_children="children")` | Если `segment` не передан — вычисляется как bounding box детей. Если `children` — список dict'ов, вызывает `_get_children_from_dict_list`. Если `segment` — dict, преобразует через `_get_segment` |
| `to_dict` | `() -> Dict` | Сериализует элемент в словарь: `{"segment": {...}, "data": {...}, name_children: [...]}`. Дети сериализуются рекурсивно |
| `from_dict` | `(dict_: Dict)` | Десериализует элемент из словаря (переинициализирует через `__init__`) |
| `_get_segment` | `(dict_segment: Dict) -> ImageSegment` | Создаёт `ImageSegment` из словаря (определяет формат по наличию ключа `"width"`) |
| `_get_dict_from_children` | `() -> List[Dict]` | Рекурсивно сериализует всех детей |
| `__get_segment_from_children` | `(children: List[PhysicalElement]) -> ImageSegment` | Вычисляет охватывающий bounding box: копирует сегмент первого ребёнка и расширяет до всех остальных |
| `_get_children_from_dict_list` | `(dict) -> List[PhysicalElement]` | **Абстрактный.** Десериализует список словарей в список дочерних элементов конкретного типа |

#### Инварианты
- `segment` всегда определён (либо передан явно, либо вычислен из children)
- Если `segment` и `children` оба `None` — выбрасывается исключение
- `children` не может быть пустым списком при вычислении `segment`

#### Иерархия name_children

| Класс | `name_children` | Тип детей | Листовой? |
|-------|-----------------|-----------|-----------|
| `Page` | `"regions"` | `List[Region]` | Нет |
| `Region` | `"rows"` | `List[Row]` | Нет |
| `Row` | `"words"` | `List[Word]` | Нет |
| `Word` | `None` | — | Да |
| `Image` | `None` | — | Да |

#### Формат сериализации (to_dict)

```json
{
    "segment": {"x_top_left": 10, "y_top_left": 20, "width": 100, "height": 50},
    "data": {"text": "Hello", "font": {...}},
    "words": [
        {
            "segment": {...},
            "data": {"text": "Hello", "font": {...}}
        }
    ]
}
```

---

### 2.3. Page

**Назначение:**  
Представляет одну страницу документа. Содержит список регионов (текстовых и нетекстовых). Является основным элементом итерации в конвейере обработки.

**Файл:** `src/pagerlib/dtypes/physical_elements/page.py`  
**Наследование:** `PhysicalElement`

#### Поля (дополнительно к PhysicalElement)

| Поле | Значение |
|------|----------|
| `name_children` | `"regions"` |
| `children` | `List[Region]` (включая `Image` как `Region` без текста) |

> **Важно:** В `children` Page могут находиться как объекты `Region`, так и `Image`. `Image` технически наследует `PhysicalElement`, а не `Region`, но на практике обе категории хранятся в едином списке `children` страницы, а код различает их по `region.children is None` (для `Image`).

#### Свойства

| Свойство | Тип | Реализация |
|----------|-----|------------|
| `text` | `str` | `"\n".join([word.text for word in self.children])` — объединяет текст всех детей через `\n` |

#### Методы

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `get_none` | `() -> Page` | Статический метод. Создаёт пустую страницу-заглушку (сегмент 0,0,1,1) |
| `_get_children_from_dict_list` | `(dict) -> List[Region]` | Десериализует список словарей в `List[Region]`, передавая каждому `segment`, `data` и children через ключ `"rows"` |

#### data-словарь
- `page.data` используется для хранения изображения страницы после этапа `PDFIMGExtractor`:
  - `data["array"]`: `np.ndarray` — RGB-изображение всей страницы в виде numpy-массива (H×W×3)

---

### 2.4. Region

**Назначение:**  
Представляет логически связный регион страницы — текстовый блок, таблицу, заголовок, изображение и т.д. Содержит список строк (Row). После этапа `Rows2Regions` получает метку `label` в `data`.

**Файл:** `src/pagerlib/dtypes/physical_elements/region.py`  
**Наследование:** `PhysicalElement`

#### Поля

| Поле | Значение |
|------|----------|
| `name_children` | `"rows"` |
| `children` | `List[Row]` |

#### data-словарь

| Ключ | Тип | Когда заполняется | Описание |
|------|-----|-------------------|----------|
| `data["label"]` | `str` | `Rows2Regions`, `MergeRegion` | Метка типа региона. Возможные значения: `"text"`, `"header"`, `"table"`, `"figure"`, `"other"` |

#### Свойства

| Свойство | Тип | Реализация |
|----------|-----|------------|
| `text` | `str` | `"\n".join([row.text for row in self.children])` — строки через перевод строки |

#### Методы

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `get_none` | `() -> Region` | Статический метод. Создаёт пустой регион-заглушку |
| `_get_children_from_dict_list` | `(dict) -> List[Row]` | Десериализует список словарей в `List[Row]` и сортирует по `y_top_left` (сверху вниз) |

---

### 2.5. Row

**Назначение:**  
Представляет строку текста в пределах региона. Содержит список слов (Word). После этапа `FontEmbExtractor` получает векторное представление шрифта.

**Файл:** `src/pagerlib/dtypes/physical_elements/row.py`  
**Наследование:** `PhysicalElement`

#### Поля

| Поле | Значение |
|------|----------|
| `name_children` | `"words"` |
| `children` | `List[Word]` |

#### data-словарь

| Ключ | Тип | Когда заполняется | Описание |
|------|-----|-------------------|----------|
| `data["font_vec"]` | `np.ndarray` | `FontEmbExtractor` | Векторное представление шрифта строки (эмбеддинг, размер зависит от модели) |

#### Свойства

| Свойство | Тип | Реализация |
|----------|-----|------------|
| `text` | `str` | `" ".join([word.text for word in self.children])` — слова через пробел |

#### Методы

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `get_none` | `() -> Row` | Статический метод. Создаёт пустую строку-заглушку |
| `_get_children_from_dict_list` | `(dict) -> List[Word]` | Десериализует список словарей в `List[Word]`. Извлекает `data` и `font` из JSON-представления. Сортирует по `x_top_left` (слева направо) |

---

### 2.6. Word

**Назначение:**  
Листовой элемент — одно слово (токен) со связанным текстом, координатами bounding box, шрифтом и (в перспективе) confidence.

**Файл:** `src/pagerlib/dtypes/physical_elements/word.py`  
**Наследование:** `PhysicalElement`

#### Поля

| Поле | Значение |
|------|----------|
| `name_children` | `None` |
| `children` | `None` |

#### data-словарь

| Ключ | Тип | Обязательность | Когда заполняется | Описание |
|------|-----|----------------|-------------------|----------|
| `data["text"]` | `str` | обязателен | `FileInput` (PDF Miner / Tesseract) | Текстовое содержимое слова |
| `data["font"]` | `Dict` | опционально | `FileInput` (PDF Miner) | Словарь с метаданными шрифта: `name`, `fontname`, `size`, `fontsize`, `height`, `width`, `is_bold`, `bold`, `italic`, `is_italic` |
| `data["confidence"]` | `float` | опционально | **планируется** | Уверенность OCR в распознавании слова (0.0 – 1.0) |

#### Свойства

| Свойство | Тип | Реализация |
|----------|-----|------------|
| `text` | `str` | `self.data["text"]` если ключ есть, иначе `""` |

#### Методы

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `get_none` | `() -> Word` | Статический метод. Создаёт пустое слово-заглушку |
| `_get_children_from_dict_list` | `(dict) -> None` | Возвращает `None` (посимвольная обработка не реализована) |

#### Инварианты
- `data["text"]` должно присутствовать и быть непустым для осмысленного слова
- `segment` определён и соответствует bounding box слова на странице

#### Формат font в data
```json
{
    "font": {
        "name": "TimesNewRoman",
        "size": 12.0,
        "width": 0.5,
        "italic": 0.0
    }
}
```

---

### 2.7. Image

**Назначение:**  
Листовой элемент — изображение (страницы целиком или нетекстового региона). Может хранить как путь к файлу, так и numpy-массив пикселей. Также используется как контейнер для пиксельного представления всей страницы после `PDFIMGExtractor`.

**Файл:** `src/pagerlib/dtypes/physical_elements/image.py`  
**Наследование:** `PhysicalElement`

#### Поля

| Поле | Значение |
|------|----------|
| `name_children` | `None` |
| `children` | `None` |

#### data-словарь

| Ключ | Тип | Когда заполняется | Описание |
|------|-----|-------------------|----------|
| `data["array"]` | `np.ndarray` | `FileInput` (изображение), `PDFIMGExtractor` | RGB-изображение в виде numpy-массива (H×W×3, dtype=uint8) |
| `data["path"]` | `str` | `FileInput` (изображение, PDF) | Путь к исходному файлу |

#### Свойства

| Свойство | Тип | Описание |
|----------|------|----------|
| `text` | `str` | Всегда `""` (для изображений текст не определён) |
| `path` | `str \| None` | `data["path"]` если есть, иначе `None` |
| `img` | `np.ndarray \| None` | `data["array"]` если есть, иначе `None` |

#### Методы

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `get_none` | `() -> Image` | Статический метод. Создаёт пустое изображение-заглушку |
| `set_img` | `(img_rgb: np.ndarray)` | Записывает массив в `data["array"]` |
| `read_img` | `(path=None) -> np.ndarray` | Статический метод. Читает изображение с диска (через OpenCV), возвращает RGB-массив |
| `plot` | `()` | Отображает `data["array"]` через `plt.imshow` |
| `_get_children_from_dict_list` | `(dict) -> None` | Возвращает `None` |

#### Автоматический segment
Если `segment` не передан, но передан `data["array"]`, то сегмент автоматически создаётся как `ImageSegment(0, 0, width, height)`, где размеры берутся из `.shape[:2]`.

> **Примечание:** При создании через `data["array"]` или `data["path"]` выводится `Warning`, сигнализирующий о наличии данных. Это отладочный механизм (не `warnings.warn`, а встроенный `Warning`).

#### Инварианты
- `data["array"]` — трёхканальный RGB (H×W×3, dtype=uint8) либо grayscale (H×W)
- `data["path"]` — строка пути, если изображение загружено из файла

---

### 2.8. PageRDF

**Назначение:**  
Корневой контейнер документа PageRLib. Агрегирует все страницы, метаданные и результаты логического анализа. Является единственной точкой входа/выхода всего конвейера обработки.

**Файл:** `src/pagerlib/dtypes/pager_doc_format.py`

#### Поля

| Поле | Тип | Назначение |
|------|-----|------------|
| `base_type` | `str \| None` | Тип исходного документа (`"pdf"`, `"image"`). В текущей версии не заполняется |
| `data` | `Dict` | Основной контейнер данных документа |
| `metadata` | `Dict` | Метаданные документа (источник, дата обработки и т.д.). В текущей версии не заполняется |

#### data-словарь — жизненный цикл

| Ключ | Тип | Когда заполняется | Описание |
|------|-----|-------------------|----------|
| `data["pages"]` | `List[Page]` | `FileInput` (всегда) | Список страниц документа. Первый и основной ключ |
| `data["path"]` | `str` | `FileInput` (PDF) | Путь к исходному файлу. Используется `PDFIMGExtractor` для рендеринга страниц |
| `data["toc"]` | `List[Section]` | `LogicalStructureExtractor` | Иерархическое оглавление документа (секции и контексты) |

#### Использование в конвейере

```python
prdf = PageRDF()
# Этап 1: FileInput
prdf.data["pages"] = [...]  # List[Page]
prdf.data["path"] = "/path/to/doc.pdf"

# Этап 2-N: PageExtractors (работают с prdf.data["pages"])
for extractor in [PDFIMGExtractor(), Words2Rows(), Rows2Regions(), MergeRegion(), FontEmbExtractor()]:
    extractor.extract(prdf)

# Этап N+1: DocumentExtractor (работает со всем prdf)
LogicalStructureExtractor().extract(prdf)
# prdf.data["toc"] = [...]  # List[Section]
```

---

### 2.9. Section

**Назначение:**  
Логический элемент структуры документа — секция (заголовок и его содержание). Образует иерархическое дерево оглавления. Создаётся на этапе `LogicalStructureExtractor`.

**Файл:** `src/pagerlib/dtypes/logical_elements/section.py`

#### Поля

| Поле | Тип | Назначение |
|------|-----|------------|
| `title` | `Region \| None` | Регион-заголовок секции. `None` для корневой секции |
| `level` | `int` | Уровень вложенности (0 — корень, 1 — заголовок верхнего уровня, и т.д.) |
| `children` | `List[Section \| Context]` | Дочерние элементы: подсекции и контексты |

#### Методы

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `__init__` | `(title: Region\|None, level=0)` | Создаёт секцию с заголовком и уровнем |
| `add_context` | `(reg: Region)` | Добавляет регион в последний Context среди children, либо создаёт новый Context |
| `to_dict` | `() -> Dict` | Сериализует секцию: `{"level": int, "title": Region.to_dict(), "children": [...]}` |

#### Инварианты
- `level >= 0`
- `children` содержит либо `Section` (подсекции), либо `Context` (контентные регионы)
- `title` не-None для всех секций, кроме корневой (root)

---

### 2.10. Context

**Назначение:**  
Логический элемент — контекст (содержимое) внутри секции. Содержит список регионов, относящихся к данной секции, но не являющихся заголовками.

**Файл:** `src/pagerlib/dtypes/logical_elements/context.py`

#### Поля

| Поле | Тип | Назначение |
|------|-----|------------|
| `children` | `List[Region]` | Список регионов, образующих содержание секции |

#### Методы

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `__init__` | `(childrens: List[Region])` | Создаёт контекст с заданным списком регионов |
| `to_dict` | `() -> Dict` | Сериализует контекст: `{"regions": [Region.to_dict(), ...]}` |

---

### 2.11. Font

**Назначение:**  
Метаданные шрифта, извлечённые из PDF или OCR. Используется `LogicalStructureExtractor` для сравнения заголовков и определения уровня секции.

**Файл:** `src/pagerlib/dtypes/physical_elements/font.py`

#### Поля

| Поле | Тип | По умолчанию | Семантика |
|------|-----|-------------|-----------|
| `name` | `str` | `""` | Название шрифта (напр. `"TimesNewRoman"`, `"Arial"`) |
| `width` | `float` | `0.5` | «Жирность» шрифта: `0.0` — обычный, `0.5` — полужирный, `1.0` — жирный. Порог для жирного: `> 0.8` |
| `italic` | `float` | `0.0` | Курсивность: `0.0` — прямой, `0.5` — полукурсив, `1.0` — курсив. Порог для курсива: `> 0.8` |
| `size` | `float` | `-1` | Размер шрифта в пунктах. `-1` означает «не определён» |

#### Методы

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `__init__` | `(dict_font: Dict)` | Создаёт Font из словаря, последовательно вызывая сеттеры |
| `set_name` | `(dict_font)` | Извлекает имя из ключа `"name"` или `"fontname"` |
| `set_width` | `(dict_font)` | Извлекает жирность из `"width"`, `"is_bold"`, или `"bold"` в имени |
| `set_italic` | `(dict_font)` | Извлекает курсивность из `"italic"`, `"is_italic"`, или `"italic"` в имени |
| `set_size` | `(dict_font)` | Извлекает размер из `"size"`, `"fontsize"`, или `"height"` |
| `to_dict` | `() -> Dict` | Сериализует: `{"name", "width", "italic", "size"}` |
| `__lt__` | `(other: Font) -> bool` | Сравнение шрифтов: этот шрифт «меньше» другого, если размер меньше на 10%+, либо он обычный а другой жирный, либо оба жирные но этот курсивный а другой нет |

#### Семантика значений width
- `1.0`: жирный (bold) — извлечён из ключа `is_bold=True` или наличия `bold` в имени шрифта
- `0.5`: стандартный (regular)
- `0.0`: обычный/лёгкий

Пороговое значение для проверки на жирность: `font.width > 0.8`.

#### Семантика значений italic
- `1.0`: курсив — извлечён из ключа `is_italic=True` или наличия `italic` в имени шрифта
- `0.5`: полукурсив/неизвестно
- `0.0`: прямой

Пороговое значение для проверки на курсив: `font.italic > 0.8`.

---

### 2.12. Graph / Node / Edge / RelatedGraph / NoneNode

**Назначение:**  
Графовые структуры для GNN-разбиения на строки (`Words2Rows`) и регионы (`Rows2Regions`). Реализуют систему непересекающихся множеств (DSU) на базе графа: вершины (слова/строки) соединяются рёбрами, после удаления рёбер (по предсказанию GNN) связанные компоненты (`RelatedGraph`) образуют итоговые группы.

**Файл:** `src/pagerlib/dtypes/relationship/segment_relationship.py`

#### Node

| Поле | Тип | Назначение |
|------|-----|------------|
| `x` | `float` | X-координата центра элемента |
| `y` | `float` | Y-координата центра элемента |
| `index` | `int` | Уникальный идентификатор вершины |
| `neighbors` | `List[Node]` | Список соседних вершин |

| Метод | Описание |
|-------|----------|
| `add_neighbor(node)` | Добавляет вершину в список соседей |
| `get_neighbors() -> Set[Node]` | Возвращает множество соседей |

#### NoneNode (наследует Node)

Вершина-заглушка с `x=None, y=None, index=None`. Используется как временный узел при операциях разделения графа.

#### Edge

| Поле | Тип | Назначение |
|------|-----|------------|
| `nodes` | `Set[Node]` | Пара вершин, соединённых ребром |

| Метод | Описание |
|-------|----------|
| `get_line() -> Tuple[List[float], List[float]]` | Возвращает координаты для отрисовки линии |
| `get_nodes() -> List[Node]` | Возвращает список из двух вершин |

#### RelatedGraph

Связный компонент графа (подграф). Карта: `nodes: Dict[Node, int]` (ключ — вершина, значение — её индекс), `edges: Dict[Tuple[int, int], Edge]`.

| Метод | Описание |
|-------|----------|
| `get_nodes() -> List[Node]` | Все вершины подграфа |
| `add_node(node, node_connect)` | Добавляет вершину и соединяет с существующей |
| `add_edge(node1, node2)` | Добавляет ребро между двумя вершинами |
| `get_edges() -> List[Edge]` | Все рёбра подграфа |
| `get_edge_from_nodes(node1, node2) -> Edge` | Получает ребро по паре вершин |
| `delete_edge(edge)` | Удаляет ребро |
| `delete_edge_from_nodes(node1, node2) -> List[RelatedGraph]` | Удаляет ребро и, если граф распался на 2 компонента, возвращает оба подграфа |
| `add_related_graph(other, this_node, other_node)` | Сливает другой подграф в текущий |
| `create_related_graph(edges_key) -> RelatedGraph` | Создаёт новый подграф из набора рёбер |

#### Graph

Основной контейнер графа. Управляет множеством `RelatedGraph`, реализуя DSU (операции union/find через добавление/удаление рёбер).

| Поле | Тип | Назначение |
|------|-----|------------|
| `related_graphs` | `Set[RelatedGraph]` | Множество всех связных компонент |
| `nodes` | `Dict[int, Node]` | Словарь всех вершин по индексу |
| `nodes_in_graphs` | `Dict[int, RelatedGraph]` | Маппинг индекс вершины → её подграф (для быстрого поиска) |
| `id_cursor` | `int` | Автоинкрементный счётчик для уникальных индексов вершин |

| Метод | Описание |
|-------|----------|
| `add_node(x, y) -> int` | Добавляет вершину, создаёт для неё новый `RelatedGraph`. Возвращает индекс |
| `add_edge(index1, index2)` | Соединяет две вершины: если в разных подграфах — сливает их |
| `delete_edge(index1, index2)` | Удаляет ребро: если подграф распадается — разделяет на два |
| `get_node(index) -> Node` | Получает вершину по индексу |
| `get_edges() -> List[Edge]` | Все рёбра графа |
| `get_nodes() -> List[Node]` | Все вершины графа |
| `get_related_graphs() -> List[RelatedGraph]` | Все связные компоненты |
| `get_related_graph_from_index_node(index) -> RelatedGraph` | Подграф, содержащий вершину с данным индексом |

#### Сценарий использования (Words2Rows / Rows2Regions)

```
1. GNN предсказывает рёбра для полносвязного графа элементов (слов/строк)
2. Удаляются рёбра, для которых E_pred > 0.5 (Words2Rows) или E_pred < 0.5 (Rows2Regions)
3. Оставшиеся связные компоненты (RelatedGraph) → группы → Row / Region
4. Для Rows2Regions дополнительно предсказывается класс каждого узла (node_classes) → label региона
```

---

## 3. Таблица жизненного цикла данных

| Этап конвейера | Модуль | Что добавляется / изменяется |
|----------------|--------|------------------------------|
| **`FileInput` (PDF — pdfminer)** | `file_input/pdf_as_json_model/` | `PageRDF.data["pages"]` — список `Page`. `Page.children` = `Image` (без pixel array) + `Region` с `Row` с `Word` (текст + `font`). `PageRDF.data["path"]` — путь к PDF |
| **`FileInput` (изображение — Tesseract)** | `file_input/tesseract/` | `PageRDF.data["pages"]` — одна `Page`. `Image` (с `data["array"]` и `data["path"]`), `Region[Row[Word]]` — результат OCR |
| **`PDFIMGExtractor`** | `extractors/page_extractor/pdf_as_img/` | `page.data["array"]` — numpy-изображение всей страницы (из PDF через pdf2image). В `page.children` в начало добавляется `Image` с этим массивом |
| **`Words2Rows`** | `extractors/page_extractor/words2rows/` | Перегруппировка `Word` → `Row` через GNN. Старые `Region` уничтожаются, все слова собираются в единый список, после GNN-разбиения создаются новые `Row`, упакованные в один `Region` |
| **`Rows2Regions`** | `extractors/page_extractor/rows2regions/` | Перегруппировка `Row` → `Region` через GNN. Создаются новые `Region` с `data["label"]` (text/header/table/figure/other) на основе классификации узлов |
| **`MergeRegion`** | `extractors/page_extractor/merge_regions/` | Слияние пересекающихся `Region`. Объединяются `Row`, метка определяется голосованием большинства |
| **`FontEmbExtractor`** | `extractors/page_extractor/font_emb_extractor/` | `row.data["font_vec"]` — векторное представление шрифта строки (np.ndarray), полученное из CNN-модели по изображению строки |
| **`LogicalStructureExtractor`** | `extractors/document_extractor/` | `PageRDF.data["toc"]` — `List[Section]`. Иерархия строится по шрифтовым признакам заголовков (размер, жирность, курсив, нумерация) |

---

## 4. Правила валидации и инварианты

### 4.1. ImageSegment
- `x_top_left < x_bottom_right` (строго, иначе `PositionException`)
- `y_top_left < y_bottom_right` (строго, иначе `PositionException`)
- Все координаты — `int` (float вызывает `TypeArgError`)
- `width >= 1`, `height >= 1`

### 4.2. PhysicalElement
- `segment` всегда определён: либо передан явно, либо вычислен как охватывающий bounding box детей
- Если `segment is None` и `children is None` → исключение
- `children` не может быть пустым списком при вычислении `segment` из детей
- Сериализация (`to_dict`) всегда использует формат точка+размер для segment

### 4.3. Word
- `data["text"]` обязательно для осмысленного слова (текст может быть пустым только для слов-заглушек)
- `name_children = None`, `children = None` — листовой элемент

### 4.4. Image
- `name_children = None`, `children = None` — листовой элемент
- Если передан `data["array"]`, segment вычисляется автоматически как `(0, 0, width, height)`
- `data["array"]` — трёхканальный RGB (H×W×3) либо grayscale (H×W)

### 4.5. Page
- `children` — список, содержащий только `Region` и `Image`
- `name_children = "regions"`
- Первым элементом `children` обычно идёт `Image` с `data["array"]` (после `PDFIMGExtractor`)

### 4.6. Иерархия PhysicalElement (строгая)
```
Page → Region → Row → Word
```
- `Page.children` — только `Region` и `Image`
- `Region.children` — только `Row`
- `Row.children` — только `Word`
- `Word.children` — `None`
- `Image.children` — `None`

### 4.7. Region
- `data["label"]` — одно из: `"text"`, `"header"`, `"table"`, `"figure"`, `"other"`
- Строки (`Row`) в регионе отсортированы по `y_top_left` (сверху вниз) при десериализации

### 4.8. Row
- Слова (`Word`) в строке отсортированы по `x_top_left` (слева направо) при десериализации
- `data["font_vec"]` — numpy-массив float, размер зависит от модели (`FontEmbExtractor`)

### 4.9. Section / Context
- `Section.level >= 0`
- `Section.children` — `List[Section | Context]`
- `Context.children` — `List[Region]`
- Корневая секция имеет `title=None, level=0`

### 4.10. Font
- `width ∈ [0.0, 1.0]` (рекомендованный диапазон)
- `italic ∈ [0.0, 1.0]` (рекомендованный диапазон)
- `size = -1` означает «не определён»
- При сравнении (`__lt__`) размер `-1` интерпретируется как `1`

---

## 5. Вспомогательные исключения

### PositionException (наследует SegmentException)

Выбрасывается при некорректных координатах (x_top_left >= x_bottom_right или y_top_left >= y_bottom_right).

### TypeArgError (наследует SegmentException)

Выбрасывается, если хотя бы одна координата имеет тип `float` (ожидаются только `int`).

### SegmentException

Базовый класс для исключений `ImageSegment`. Хранит все четыре координаты, вызвавшие ошибку.

---

## 6. Схема взаимодействия типов

```
                          PageRDF
                         /   |    \
                   data["pages"] |  data["toc"]
                        |    data["path"]   |
                   List[Page]        List[Section]
                        |                   /      \
                   Page.children      Section    Context
                    /        \       (title,    (regions)
              Image        Region    level,
              (array,      (label,   children)
               path)       rows)
                               |
                            List[Row]
                          (font_vec)
                               |
                           List[Word]
                          (text, font, confidence*)

*планируется
```

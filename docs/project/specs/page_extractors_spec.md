# Спецификация: Постраничные экстракторы PageRLib

**Версия:** 1.0-draft
**Дата:** 2026-07-16
**Статус:** Спецификация существующего кода
**Модуль:** `src/pagerlib/extractors/page_extractor/`

---

## 1. Архитектурные принципы

### 1.1 Базовый класс `BasePageExtractor`

Файл: `base_page_extractor.py`

```python
class BasePageExtractor(ABC):
    @abstractmethod
    def page_extract(self, page):
        """Обработка одной страницы. Переопределяется в субклассах."""

    def extract(self, prdf: PageRDF):
        """Итерация по всем страницам документа.
        1. Для каждой страницы вызывает self.page_extract(page)
        2. После каждой страницы вызывает sorter(page)
        """
```

**Паттерн проектирования:** Template Method — `extract()` задаёт скелет алгоритма (итерация + сортировка), субклассы переопределяют `page_extract()`.

**Глобальный сортировщик:**

```python
# base_page_extractor.py
sorter = RegionSorterCutXYExtractor()
```

Гарантирует порядок чтения (слева-направо, сверху-вниз) после каждого этапа обработки страницы.

### 1.2 Принцип 1: In-place модификация

Каждый экстрактор модифицирует переданный объект `PageRDF` (и вложенные `Page`) на месте. Метод `extract()` **не возвращает** значение — все изменения производятся через мутацию переданного объекта:

```python
# Типичное использование (возвращаемое значение игнорируется):
pdf_img_extractor.extract(prdf)  # prdf модифицирован на месте
words2rows.extract(prdf)         # prdf модифицирован на месте
```

Копирования данных между этапами не происходит.

### 1.3 Принцип 2: Разделение text_regions и no_text_regions

Большинство экстракторов разделяют `page.children` на две категории:

| Категория | Условие | Содержимое |
|-----------|---------|------------|
| `text_regions` | `region.children is not None` | `Region` с детьми (`Row` → `Word`), содержит текст |
| `no_text_regions` | `region.children is None` | `Image` или `Region` без детей (листовые элементы) |

После обработки выполняется пересборка:

```python
page.children = no_text_regions + text_regions
```

Это гарантирует, что изображения и другие не-текстовые элементы сохраняются и не теряются между этапами конвейера.

### 1.4 Принцип 3: Сортировка после каждого этапа

`RegionSorterCutXYExtractor` вызывается в `BasePageExtractor.extract()` после обработки каждой страницы:

```python
def extract(self, prdf: PageRDF):
    for page in prdf.data['pages']:
        self.page_extract(page)
        sorter(page)  # ← сортировка после каждого page_extract
```

---

## 2. Спецификация экстракторов

### 2.1 `PDFIMGExtractor` — рендеринг PDF-страниц в изображения

**Файл:** `pdf_as_img/pdf_as_img.py`
**Назначение:** конвертирует PDF-файл в numpy-изображения для каждой страницы.
**Наследование:** `BasePageExtractor`

#### `extract(self, prdf: PageRDF)`

Переопределяет базовый метод. Алгоритм:

1. `pdf2image.convert_from_path(prdf.data['path'])` → `List[PIL.Image]` (по одному на страницу)
2. Для каждой страницы документа:
   - Если `page.data is None` → `page.data = {}`
   - `page.data['array'] = np.array(pil)`
3. Вызывает `super().extract(prdf)` — базовый цикл по страницам (page_extract + sorter)

#### `page_extract(self, page: Page)`

1. Изменяет размер изображения до размеров страницы: `cv2.resize(page.data['array'], (page.segment.width, page.segment.height))`
2. Создаёт `Image(data={'array': resized_img})`
3. Добавляет в начало списка: `page.children = [img] + page.children`

**Предусловие:** `prdf.data['path']` должен указывать на существующий PDF-файл.

**Результат:** `page.data['array']` содержит `np.ndarray` (RGB), `page.children[0]` — `Image` с тем же массивом.

---

### 2.2 `Words2Rows` — группировка слов в строки (GNN)

**Файл:** `words2rows/words2rows.py`
**Назначение:** перегруппировка слов в логические строки с помощью графовой нейросети.
**Наследование:** `BasePageExtractor`

#### Конструктор

```python
def __init__(self, conf={}):
    self.words2rowsGLAM_tokenizer = WordGLAMTokenizer()
    self.words2rowsGLAM = get_load_model()
```

#### `page_extract(self, page: Page)`

1. **Разделение:** `text_regions` (children не None) / `no_text_regions` (children is None)
2. **Сбор слов:** `[word for region in text_regions for row in region.children for word in row.children]`
3. **Формирование JSON:** каждый word → `{"text": word.text, "segment": word.segment.get_segment_2p()}`
4. **Ветвление по количеству слов:**
   - 0 слов → `row_list = []`
   - 1 слово → `row_list = [Row(children=words)]`
   - ≥ 2 слов → запуск GNN-конвейера `self.get_row(words_json, words)`
5. **Пересборка:** `page.children = no_text_regions + [Region(children=row_list)]`

> **Важно:** все строки оборачиваются в **один** `Region`. Дальнейшая группировка в семантические регионы выполняется на следующем этапе (`Rows2Regions`).

#### GNN-конвейер `get_row(words_json, words)`

```
┌─────────────────────────────────────────────────────────┐
│                    Words2Rows GNN Pipeline               │
├─────────────────────────────────────────────────────────┤
│ 1. WordGLAMTokenizer(words_json)                        │
│    ├─ graph_creat(): построение рёбер по близости       │
│    ├─ get_node_features(): 15-мерный вектор на слово     │
│    └─ get_edge_features(): 4-мерный вектор на ребро      │
│                                                         │
│ 2. TorchModel.forward(graph_dict_torch)                 │
│    ├─ NodeGLAM (TAGConv + skip connections)             │
│    └─ EdgeGLAM (MLP над парами узлов + edge_feat)       │
│    → {E_pred: Tensor[N_edges]}                          │
│                                                         │
│ 3. Пороговая фильтрация:                                │
│    deleted_edges = E_pred > 0.5                         │
│    (E_pred > 0.5 → слова в разных строках → удалить)    │
│                                                         │
│ 4. Union-Find на оставшихся рёбрах:                     │
│    Graph().add_node() + add_edge() для не-удалённых     │
│    → get_related_graphs() → компоненты связности         │
│                                                         │
│ 5. Каждая компонента → Row(children=words_in_component) │
└─────────────────────────────────────────────────────────┘
```

**Модель:** `words2rows_glam_20260113/` — предобученная, загружается через `get_load_model()`.

---

### 2.3 `Rows2Regions` — группировка строк в регионы + классификация (GNN)

**Файл:** `rows2regions/rows2regions.py`
**Назначение:** объединение строк в семантические регионы и классификация типа каждого региона.
**Наследование:** `BasePageExtractor`

#### Конструктор

```python
def __init__(self):
    self.model = get_load_model()
    self.tokenizer = RowGLAMTokenizer()
```

#### Классы регионов

```python
CLASSES = {
    0: 'other',
    1: 'text',
    2: 'header',
    3: 'text',    # дубль класса 1
    4: 'table',
    5: 'figure'
}
```

#### `page_extract(self, page: Page)`

1. **Разделение:** `text_regions` / `no_text_regions` (по `children is not None`)
2. **Сбор строк:** каждая строка → `{"text", "segment", "words": [word.to_dict() for word in row.children]}`
3. **Ветвление по количеству строк:**
   - 0 строк → `region_list = []`
   - 1 строка → `region_list = [Region(children=rows, data={'label': CLASSES[0]})]` — метка `'other'`
   - ≥ 2 строк → запуск GNN-конвейера `self.get_region(rows_json)`
4. **Пересборка:** `page.children = no_text_regions + region_list`

#### GNN-конвейер `get_region(rows_json)`

```
┌─────────────────────────────────────────────────────────────┐
│                 Rows2Regions GNN Pipeline                    │
├─────────────────────────────────────────────────────────────┤
│ 1. RowGLAMTokenizer(rows_json)                              │
│    ├─ graph_creat(): построение рёбер по близости строк      │
│    ├─ get_node_features(): 15-мерный вектор на строку        │
│    └─ get_edge_features(): 4-мерный вектор на ребро          │
│                                                             │
│ 2. TorchModelBase.forward(graph_dict_torch)                 │
│    ├─ NodeGLAM (TAGConv + классификационная голова)          │
│    └─ EdgeGLAM (MLP: cat(node_i, node_j, X_i, X_j, edge))   │
│    → {node_classes: Tensor[N×6], E_pred: Tensor[N_edges]}   │
│                                                             │
│ 3. Пороговая фильтрация рёбер:                              │
│    deleted_edges = E_pred < 0.5                              │
│    (E_pred < 0.5 → строки в разных регионах → удалить)       │
│                                                              │
│ 4. Union-Find на оставшихся рёбрах → компоненты связности    │
│                                                              │
│ 5. Классификация компоненты:                                │
│    label = CLASSES[argmax(mean(node_classes[component]))]    │
│                                                              │
│ 6. Каждая компонента →                                      │
│    Region(children=rows_in_component, data={'label': label}) │
└─────────────────────────────────────────────────────────────┘
```

> **Различие порогов:** `Words2Rows` удаляет рёбра при `E_pred > 0.5` (высокая уверенность = разные строки), а `Rows2Regions` удаляет рёбра при `E_pred < 0.5` (низкая уверенность = разные регионы). Модели обучены с разной семантикой предсказания.

**Модель:** `rows2region_glam_20260225/` — предобученная, загружается через `get_load_model()`.

---

### 2.4 `MergeRegion` — слияние пересекающихся регионов

**Файл:** `merge_regions/merge_regions.py`
**Назначение:** объединение регионов с одинаковым `label`, которые пересекаются геометрически.
**Наследование:** `BasePageExtractor`

#### `page_extract(self, page: Page)`

1. **Разделение:** `text_regions` / `no_text_regions`
2. Вызов `self.merge(text_regions)` → список объединённых регионов
3. **Пересборка:** `page.children = no_text_regions + new_regions`

#### `merge(self, regions: List[Region]) -> List[Region]`

1. Извлекает `ImageSegment` из каждого региона
2. Вызывает `merge_segment(segs)` → `List[int]` — маппинг индекса в группу
3. Группирует индексы регионов по идентификатору группы
4. Для каждой группы:
   - **Расширение bounding box:** `segment.set_segment_max_segments([все сегменты группы])`
   - **Определение метки большинством:** `Counter(labels).most_common(1)[0][0]`
   - **Объединение детей:** все `Row` из всех регионов группы
   - Создаёт `Region(children=combined_rows, data={'label': majority_label})`

#### Алгоритм `merge_segment(segs: List[ImageSegment]) -> List[int]`

**Файл:** `merge_regions/merge_segment.py`

Итеративный O(n²) алгоритм слияния пересекающихся bounding box-ов:

```python
def merge_segment(segs):
    array_ind = list(range(len(segs)))  # индекс группы для каждого сегмента
    array_segs = [копия seg]            # рабочие копии сегментов

    change = True
    while change:
        change = False
        for i, j in все_пары_индексов:
            if array_segs[i].is_intersection(array_segs[j]):
                # Расширить i до охвата обоих
                array_segs[i].set_segment_max_segments([array_segs[j], array_segs[i]])
                array_segs[j] = array_segs[i]   # j теперь ссылается на тот же объект
                array_ind[j] = array_ind[i]      # j приписан к группе i
                change = True

    # Перенумерация групп в连续的 индексы
    return compact_indices(array_ind)
```

---

### 2.5 `FontEmbExtractor` — извлечение эмбеддингов шрифтов

**Файл:** `font_emb_extractor/font_emb_extractor.py`
**Назначение:** получение векторного представления шрифта для каждой строки текста.
**Наследование:** `BasePageExtractor`
**Требует:** `PDFIMGExtractor` должен быть выполнен первым (нужен `page.children[0].data['array']`).

#### Конструктор

```python
SIZES = (512, 32, 16)

class FontEmbExtractor(BasePageExtractor):
    def __init__(self, size=512):
        # size ∈ {512, 32, 16}
        # 512: полноразмерные эмбеддинги (ResNet18 выход после пулинга → 512-dim)
        # 32:  сжатые (ResNet18 → Linear(512→32) → 32-dim)
        # 16:  сильно сжатые (ResNet18 → Linear(512→16) → 16-dim)
        self.model = load_model(size)
```

#### `page_extract(self, page: Page)`

1. Получает изображение страницы: `image = page.children[0].data['array']`
   > Предполагает, что первый ребёнок — `Image` с массивом пикселей (результат `PDFIMGExtractor`)
2. Для каждого `region` в `page.children`:
   - Пропускает, если `region.children is None` (не-текстовые элементы)
   - Для каждого `row` в `region.children`:
     - Вырезает изображение строки: `row.segment.get_segment_from_img(image)`
     - Конвертирует RGB → Grayscale: `cv2.cvtColor(row_img, cv2.COLOR_RGB2GRAY)`
     - Конвертирует в PIL: `Image.fromarray(row_cv2)`
     - Прогоняет через модель: `row_to_vec(model, pil_image)` → `torch.Tensor`
     - Если `row.data is None` → `row.data = {}`
     - Сохраняет: `row.data['font_vec'] = vec.numpy()`

#### Модель шрифтового идентификатора

**Файл:** `font_emb_extractor/font_identifier.py`

```
ResNet18 (pretrained on ImageNet)
  ├─ backbone (features): заморожен
  ├─ fc: заменён в зависимости от size
  │   ├─ size=512: fc = Linear(512→71); после загрузки весов → Identity()
  │   └─ size∈{32,16}: fc = Sequential(Linear(512→size), Linear(size→71));
  │                    после загрузки → последний слой → Identity()
  │
  └─ Выход: эмбеддинг размерности size
```

**Предобработка изображения строки (`row_to_vec`):**

```
PIL Image (Grayscale)
  → Grayscale(3 channels)   # дублирование канала
  → Resize(18)
  → CenterCrop((18, 112))
  → ToTensor()
  → Normalize(ImageNet stats)
  → model.forward() → vector размерности size
```

**Файлы моделей:** `font_identifier_model_lines_{size}.pth`

---

## 3. Вспомогательные компоненты

### 3.1 Tokenizer-ы для GNN

#### `WordGLAMTokenizer`

**Файл:** `words2rows/wordGLAM_tokenizer_20260113/wordGLAM_tokenizer.py`

Вход: `words_json` — список словарей `[{"text": str, "segment": dict_2p}]`

Выход: `{"N": int, "X": Tensor[N×15], "Y": Tensor[E×4], "sp_A": sparse[N×N], "inds": [A1, A2]}`

#### `RowGLAMTokenizer(BaseTokenizer)`

**Файл:** `rows2regions/rowsGLAM_tokenizer_20260225/rowsGLAM_tokenizer.py`

Наследует `BaseTokenizer(ABC)` (абстрактные `get_dict_vec()`, `get_name()`).

Вход: `rows_json` — список словарей `[{"text": str, "segment": dict_2p, "words": [...]}]`  
Дополнительный параметр `pdf_img` (зарезервирован, не используется в текущей реализации).

Выход: тот же формат, что и `WordGLAMTokenizer`.

#### Признаки узлов (15-dim)

| Индексы | Название | Описание |
|---------|----------|----------|
| 0–5 | `coord_vec` | `[x_top_left, x_bottom_right, width, y_top_left, y_bottom_right, height]` |
| 6–9 | `dot_vec` | Индикаторы пунктуации: `[".", ",", ";", ":"]` — 1.0 если символ есть в тексте |
| 10–11 | `super_vec` | Регистр: `[is_all_uppercase, is_title_case]` |
| 12 | `list_ind_vec` | Маркер списка: 1 если текст совпадает с одним из 25+ regex-паттернов |
| 13–14 | `heuristics_vec` | `[len(text) / (width/height), digit_count / len(text)]` |

#### Признаки рёбер (4-dim)

| Индекс | Название | Вычисление |
|--------|----------|------------|
| 0 | `angle_center` | `abs(cos(угла между центрами r1 и r2))` — `ImageSegment.get_angle_center()` |
| 1 | `min_dist` | Минимальное L2-расстояние между углами bbox — `ImageSegment.get_min_dist()` |
| 2 | `abs(dx)` | `abs(x_center_1 - x_center_2)` |
| 3 | `abs(dy)` | `abs(y_center_1 - y_center_2)` |

#### Построение графа `graph_creat(segments)`

Эвристический алгоритм построения разреженного графа соседства:

- **`fun_dist_bottom`:** для каждого сегмента ищет ближайшего соседа **снизу** (yc_this < yc_other). Расстояние = yd, если выровнены по X (right/left/center в пределах 3px), иначе xd+yd.
- **`fun_dist_right`:** для каждого сегмента ищет ближайшего соседа **справа** (xc_this < xc_other). Проверяет вертикальное перекрытие (yd ≤ 2h), расстояние = xd+yd.
- Рёбра = `set(dists_bottom + dists_right)` — уникальные неориентированные пары.

---

### 3.2 GNN-модели

#### `TorchModel` (Words2Rows)

**Каталог:** `words2rows/words2rows_glam_20260113/`

- **`NodeGLAM`:** TAGConv слои с skip connections — агрегируют информацию по графу
- **`EdgeGLAM`:** MLP, принимающий конкатенацию `[node_emb_i, node_emb_j, X_i, X_j, edge_feat_ij]`
- **Выход:** `{"E_pred": Tensor[E]}` — вероятности того, что ребро нужно удалить

#### `TorchModelBase` (Rows2Regions)

**Каталог:** `rows2regions/rows2region_glam_20260225/`

- **`NodeGLAM`:** TAGConv + классификационная голова (6 классов)
- **`EdgeGLAM`:** та же архитектура, что и в TorchModel
- **Выход:** `{"node_classes": Tensor[N×6], "E_pred": Tensor[E]}`

---

## 4. Полный конвейер обработки страницы

```
Исходный PageRDF (после FileInput — PDF или изображение)
  │  prdf.data['pages']: list[Page]
  │  Page.children = [Image, Image, Region[Row[Word...]], ...]
  │
  ├─ Шаг 1: PDFIMGExtractor.extract(prdf)
  │   ├─ pdf2image.convert_from_path(prdf.data['path']) → List[PIL.Image]
  │   ├─ page.data['array'] = np.array(pil)               ← рендеринг страницы в numpy
  │   └─ page.children = [Image(data={'array': array}), ...]  ← изображение в детях
  │
  ├─ Шаг 2: Words2Rows.extract(prdf)
  │   ├─ Сбор всех Word из text_regions
  │   ├─ GNN: предсказание рёбер между словами
  │   ├─ Union-Find → новые Row
  │   └─ page.children = [Image, Image, Region[Row[Word...]]]
  │
  ├─ Шаг 3: Rows2Regions.extract(prdf)
  │   ├─ Сбор всех Row из text_regions
  │   ├─ GNN: предсказание рёбер + классификация узлов
  │   ├─ Union-Find → новые Region с label
  │   └─ page.children = [Image, Image, Region(label='text'), Region(label='header'), ...]
  │
  ├─ Шаг 4: MergeRegion.extract(prdf)
  │   ├─ merge_segment(): итеративное слияние пересекающихся bbox
  │   ├─ Голосование большинством для label
  │   └─ page.children = [Image, Image, Region(label='text', объединённый), ...]
  │
  └─ Шаг 5: FontEmbExtractor.extract(prdf)
      ├─ Получение page.children[0].data['array'] — изображение страницы
      ├─ Для каждой Row: crop → grayscale → ResNet18 → вектор
      └─ row.data['font_vec'] = numpy_vector
```

---

## 5. Правила и инварианты

| Правило | Описание |
|---------|----------|
| Порядок экстракторов | PDFIMGExtractor → Words2Rows → Rows2Regions → MergeRegion → FontEmbExtractor |
| Обязательность PDFIMGExtractor | Требуется перед FontEmbExtractor (нужен `page.children[0].data['array']`) |
| Сохранение Image | Все экстракторы сохраняют `no_text_regions` (элементы с `children is None`) без изменений |
| In-place | Все методы `extract()` модифицируют переданный объект, **не возвращая** его копию |
| Сортировка | После каждого `page_extract` вызывается `sorter(page)` |
| GNN fallback | Если слов ≤ 1 (Words2Rows) или строк ≤ 1 (Rows2Regions), GNN не используется |
| Fallback-метка Rows2Regions | Единственная строка получает метку `'other'` (CLASSES[0]) |
| Обёртка Words2Rows | Все строки оборачиваются в **один** `Region`, независимо от их количества |
| Обработка ошибок GNN | При ошибке модели исключение пробрасывается наверх |

---

## 6. Классификация регионов (Rows2Regions)

| ID класса | Метка | Описание |
|-----------|-------|----------|
| 0 | `other` | Прочее (включая fallback для одиночных строк) |
| 1 | `text` | Основной текст |
| 2 | `header` | Заголовок |
| 3 | `text` | Текст (дубль класса 1) |
| 4 | `table` | Таблица |
| 5 | `figure` | Рисунок / подпись |

Метка сохраняется в `Region.data['label']`.

Классификация принимается большинством голосов внутри компоненты связности:

```python
label = CLASSES[np.argmax(row_classes.mean(axis=0))]
```

---

## 7. Структура файлов модуля

```
src/pagerlib/extractors/page_extractor/
├── __init__.py                          # Экспорт всех классов
├── base_page_extractor.py               # BasePageExtractor + глобальный sorter
│
├── pdf_as_img/
│   └── pdf_as_img.py                    # PDFIMGExtractor
│
├── words2rows/
│   ├── words2rows.py                    # Words2Rows
│   ├── wordGLAM_tokenizer_20260113/
│   │   └── wordGLAM_tokenizer.py        # WordGLAMTokenizer + graph_creat()
│   └── words2rows_glam_20260113/        # TorchModel + get_load_model()
│
├── rows2regions/
│   ├── rows2regions.py                  # Rows2Regions + CLASSES
│   ├── rowsGLAM_tokenizer_20260225/
│   │   └── rowsGLAM_tokenizer.py        # RowGLAMTokenizer(BaseTokenizer) + graph_creat()
│   └── rows2region_glam_20260225/       # TorchModelBase + get_load_model()
│
├── merge_regions/
│   ├── merge_regions.py                 # MergeRegion
│   └── merge_segment.py                 # merge_segment() — итеративное слияние bbox
│
└── font_emb_extractor/
    ├── font_emb_extractor.py            # FontEmbExtractor + SIZES
    ├── font_identifier.py               # load_model(), row_to_vec()
    └── font_identifier_model_lines_{512,32,16}.pth  # Веса ResNet18
```

---

## 8. Связь с документными экстракторами

Хотя это не постраничные экстракторы, показана архитектурная связь:

### `BaseDocumentExtractor`

```python
class BaseDocumentExtractor(ABC):
    @abstractmethod
    def document_extract(self, prdf: PageRDF):
        """Обработка всего документа."""

    def extract(self, prdf: PageRDF):
        prdf.data['toc'] = self.document_extract(prdf)
```

Паттерн аналогичен `BasePageExtractor`: Template Method, где `document_extract` — переопределяемый шаг, результат сохраняется в `prdf.data['toc']`.

### `LogicalStructureExtractor`

Собирает все `text_regions` со всех страниц (пропускает `no_text_regions`):
- Для каждого `header`-региона создаёт `Section`, определяет уровень вложенности через сравнение шрифтов
- Для не-header регионов добавляет в `Context` текущей `Section`
- Результат: `prdf.data['toc']` — дерево `Section`/`Context`

---

## 9. Обработка ошибок

| Ситуация | Поведение |
|----------|-----------|
| PDF-файл не существует | `pdf2image.convert_from_path()` пробрасывает исключение |
| GNN-модель не загружена | `torch.load()` пробрасывает `FileNotFoundError` / `RuntimeError` |
| `page.data is None` в PDFIMGExtractor | Инициализируется пустым `{}` |
| `row.data is None` в FontEmbExtractor | Инициализируется пустым `{}` |
| 0 слов/строк | Пустой результат без вызова GNN |
| 1 слово/строка | Прямая обёртка в `Row` / `Region` без GNN |
| `region.children is None` | Пропускается как `no_text_region` |
| Неверный `size` в FontEmbExtractor | `Exception(f"Exists only {SIZES}")` |

---

## 10. Связанные документы

| Документ | Путь |
|----------|------|
| Спецификация Image Extractor | `docs/project/specs/image_extractor_spec.md` |
| Типы данных (PageRDF) | `src/pagerlib/dtypes/pager_doc_format.py` |
| Физические элементы | `src/pagerlib/dtypes/physical_elements/` |
| ImageSegment | `src/pagerlib/dtypes/image_segment.py` |
| Graph (Union-Find) | `src/pagerlib/dtypes/relationship/` |

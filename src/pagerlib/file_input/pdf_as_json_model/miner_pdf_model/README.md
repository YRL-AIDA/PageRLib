# Miner PDF Model

Извлекает структуру из PDF-документов с помощью pdfminer.six.

## Архитектура

```
FileInput(path)
  └─> read_pdf("miner", path)
       └─> MinerPDFModel.read_from_file(path)
            └─> PDFStructureExtractor.extract_from_path(path)
                 ├─ Открывает PDF → PDFDocument, PDFResourceManager
                 ├─ _FastPDFPageAggregator (ускоренный сборщик элементов)
                 ├─ Для каждой страницы:
                 │   ├─ PDFPageInterpreter.process_page(page)
                 │   │   └─ _FastPDFPageAggregator.paint_path()
                 │   │       └─ Собирает только bounding box пути (не создаёт LTCurve)
                 │   ├─ get_result() → LTPage (layout-дерево)
                 │   └─ _process_page(layout, path_bboxes)
                 │       ├─ Классификация элементов: текст, изображения, фигуры
                 │       ├─ _merge_path_bboxes() — occupancy grid + BFS
                 │       ├─ _process_text_line() / _process_image()
                 │       └─ Возвращает {rows, images}
                 └─ Возвращает {document, pages}
```

## Типы элементов и их обработка

| Тип pdfminer        | Как обрабатывается                                     | Результат       |
|----------------------|--------------------------------------------------------|-----------------|
| `LTTextLine`         | `_process_text_line()` → слова, координаты             | `rows[]`        |
| `LTChar` (без строк) | `_chars_to_text_lines()` → группировка в строки        | `rows[]`        |
| `LTImage`            | `_process_image()` → bounding box                      | `images[]`      |
| `LTFigure`           | `_extract_visual_from_figure()` → рекурсивный разбор   | `images[]`      |
| Пути (lines/curves)  | `_merge_path_bboxes()` → occupancy grid + BFS         | `images[]`      |

## Обработка векторных элементов (paths/curves)

### Проблема
Стандартный `PDFPageAggregator.paint_path()` создаёт объекты `LTCurve`/`LTLine`/`LTRect` для
каждого пути в PDF. При большом количестве путей (300k+) это создаёт огромный overhead
по памяти и времени. `_FastPDFPageAggregator` переопределяет `paint_path()`, собирая
только bounding box каждого пути — без создания полноценных объектов. Это O(1) на путь.

### Occupancy grid merging
После сбора всех bbox'ов путей, они сливаются в цельные визуальные элементы через
occupancy grid:

1. **Разметка сетки**: страница делится на ячейки `GRID_CELL_SIZE × GRID_CELL_SIZE` px.
   Каждый path bbox дилатируется на `GRID_DILATION` px и помечает занятые ячейки.
2. **Connected components**: BFS с 8-связностью находит связные компоненты в сетке.
3. **Фильтрация декоративных линий**: компоненты с aspect ratio > 15 и занимающие >50%
   страницы отфильтровываются (типичные разделительные линии).

Сложность: O(n) по количеству путей. 228k путей обрабатываются за <0.2с.

### Разделение по контексту (begin_figure/end_figure)
Пути внутри разных `LTFigure`-контейнеров обрабатываются раздельно:
- Пути одной фигуры (схема/диаграмма) → сливаются в одно изображение
- Пути разных фигур → остаются раздельными (линии таблиц, отделённые от диаграмм)
- Пути вне фигур (top-level) → обрабатываются вместе

## Координатная система

Все координаты проходят через единое преобразование `_get_coords()`:
- **Вход**: bbox в PDF-points (device space, Y вверх)
- **Выход**: пиксельные координаты (X слева, Y сверху)
- **Масштаб**: 1 point = 1 px при DPI=72

Текст и изображения используют одну и ту же систему координат.

## Константы

Все магические числа вынесены как class-level константы в `PDFStructureExtractor`:
- `GRID_CELL_SIZE`, `GRID_DILATION` — параметры occupancy grid
- `DECO_LINE_*` — фильтр декоративных линий
- `MERGE_OVERLAP_PAD` — отступ при проверке пересечений
- `MIN_LTIMAGE_SIZE`, `MIN_NON_IMAGE_SIZE` — минимальные размеры
- `MAX_TEXT_HEIGHT` — максимальная высота текстовой строки
- И т.д.

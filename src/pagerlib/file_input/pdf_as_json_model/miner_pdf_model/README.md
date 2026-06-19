# Miner PDF Model

Извлекает структуру из PDF-документов с помощью pdfminer.six.

## Архитектура

Извлечение разделено на две логические фазы внутри одного прохода pdfminer:

```
FileInput(path)
  └─> read_pdf("miner", path)
       └─> MinerPDFModel.read_from_file(path)
            └─> PDFStructureExtractor.extract_from_path(path)
                 ├─ Открывает PDF → PDFDocument, PDFResourceManager
                 ├─ _FastPDFPageAggregator (собирает path bboxes, избегает LTCurve)
                 ├─ Для каждой страницы — единый проход pdfminer:
                 │   ├─ PDFPageInterpreter.process_page(page)
                 │   │   ├─ _FastPDFPageAggregator.paint_path()
                 │   │   │   └─ O(1) bbox вместо создания LTCurve-объектов
                 │   │   └─ Текст + изображения обрабатываются стандартно
                 │   ├─ get_result() → LTPage (layout-дерево)
                 │   └─ _process_page(layout, path_bboxes):
                 │       ├─ Фаза 1 — текст:
                 │       │   ├─ _classify_visual_elements() → text_lines, page_chars
                 │       │   └─ _extract_text_rows() → rows[]
                 │       └─ Фаза 2 — визуал:
                 │           ├─ merge_path_bboxes() — grid union-find
                 │           ├─ merge_overlapping_images() — overlap merge
                 │           └─ _extract_image_infos() → images[]
                 └─ Возвращает {document, pages}
```

## Два режима агрегатора

| Агрегатор               | Назначение                                        |
|--------------------------|---------------------------------------------------|
| `_TextOnlyAggregator`    | Только текст + изображения, `paint_path` — no-op  |
| `_FastPDFPageAggregator` | Полный сбор: текст + path bboxes (без LTCurve)    |

`_TextOnlyAggregator` доступен для случаев, когда нужна только текстовая
разметка.  Основной поток использует `_FastPDFPageAggregator` в один проход,
извлекая текст первым, затем визуальные элементы — это оптимально по времени
(один парсинг content stream вместо двух).

## Типы элементов и их обработка

| Тип pdfminer        | Как обрабатывается                                     | Результат       |
|----------------------|--------------------------------------------------------|-----------------|
| `LTTextLine`         | `process_text_line()` → слова, координаты              | `rows[]`        |
| `LTChar` (без строк) | `chars_to_text_lines()` → группировка в строки         | `rows[]`        |
| `LTImage`            | `process_image()` → bounding box                      | `images[]`      |
| `LTFigure`           | `extract_from_figure()` → рекурсивный разбор           | `images[]`      |
| Пути (lines/curves)  | `merge_path_bboxes()` → morphological merge  | `images[]`      |

## Обработка векторных элементов (paths/curves)

### Проблема
Стандартный `PDFPageAggregator.paint_path()` создаёт объекты `LTCurve`/`LTLine`/`LTRect` для
каждого пути в PDF. При большом количестве путей (200k+) это создаёт огромный overhead
по памяти и времени. `_FastPDFPageAggregator` переопределяет `paint_path()`, собирая
только bounding box каждого пути — без создания полноценных объектов. Это O(1) на путь.

### Morphological merge

После сбора bbox'ов путей они сливаются в цельные визуальные элементы через
морфологическую обработку (OpenCV):

1. **Рендер в canvas**: каждый bbox рисуется как заполненный прямоугольник
   на бинарном изображении (масштаб ×2 от размера страницы).
2. **Фильтрация широких путей**: пути шире или выше 50% страницы отбрасываются —
   это разделительные линии или общие рамки вокруг нескольких графиков.
3. **Morphological closing**: эллиптическое ядро (радиус 10 пикселей в исходном
   масштабе) закрывает промежутки между элементами внутри одного графика, но не
   соединяет отдельные графики (разделённые пустым пространством >20px).
4. **Connected components**: каждая связная область → отдельный bounding box.
    Области меньше 500 px² (в масштабе ×2) отфильтровываются как шум.

Сложность: O(P + W·H·log(R)), где P — количество путей, W·H — размер canvas,
R — радиус closing-ядра.

Пути шире или выше 50% страницы (например, разделительные линии между графиками)
отфильтровываются перед рендером — это предотвращает слияние соседних графиков
через общие элементы.

## Быстрый парсер путей (fast_path_parser)

Модуль `fast_path_parser.py` содержит экспериментальный парсер, извлекающий bbox'ы путей
напрямую из сырого content stream, минуя PS-парсер pdfminer. Работает в 2.6× быстрее
на парсинге путей (8s против 21s для 31 MB content stream), **но не используется
по умолчанию** — так как pdfminer всё равно должен парсить content stream для извлечения
текста, двойной парсинг увеличивает общее время.

Может быть полезен для PDF без текста (только графика) или при замене pdfminer на другую
библиотеку для текста.

## Режим отладки

```python
ext = PDFStructureExtractor(debug_timing=True)
```

Выводит для каждой страницы: время парсинга, обработки, количество путей/строк/изображений.

Скрипт `tests/speed_test/debug_pdf.py` позволяет протестировать любой PDF с таймаутом:

```bash
python tests/speed_test/debug_pdf.py path/to/file.pdf [timeout_seconds]
```

## Координатная система

Все координаты проходят через единое преобразование `get_coords()`:
- **Вход**: bbox в PDF-points (device space, Y вверх)
- **Выход**: пиксельные координаты (X слева, Y сверху)
- **Масштаб**: 1 point = 1 px при DPI=72

Текст и изображения используют одну и ту же систему координат.

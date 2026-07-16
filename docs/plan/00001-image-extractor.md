# Этап 1: Image Extractor — OCR-обработка изображений документа

**Глобальный план:** [global.md](./global.md)  
**Дата создания:** 2026-07-16  
**Дата ревизии:** 2026-07-16  
**Статус:** ADR-001 принят, ADR-002 принят, ADR-003 принят, ADR-004 принят  

---

## Цель

Реализовать экстрактор `Images2RegionsExtractor`, который принимает `PageRDF` (с уже загруженными изображениями без OCR-текста), обходит все изображения в документе и применяет Tesseract OCR к каждому. Возвращает дополненный `PageRDF`: изображения получают текстовые `Region` с confidence scores.

Ключевой принцип: **`FileInput` загружает документ как есть** (изображение → только `Image`-регион; PDF → текст PDFMiner + метаданные изображений). **`Images2RegionsExtractor` добавляет OCR-текст** к изображениям. Это разделение ответственности: чтение ≠ обработка.

## Обзор

**Текущее состояние:**

| Компонент | Что делает |
|-----------|------------|
| `file_input/tesseract/image2words.py` | `Image2Words` — OCR одного `np.ndarray` через Tesseract, возвращает слова с bbox |
| `file_input/tesseract/image_read.py` | `read_image()` — загружает файл, создаёт `Image`, делает OCR, возвращает `PageRDF` с текстом |
| `file_input/file_input.py` | `FileInput` — роутинг: PDF → `pdf_reader()` (MinerPDFModel), изображения → `image_reader()` (`read_image()`) |
| `file_input/pdf_as_json_model/pdf_read.py` | `read_pdf()` — создаёт `PageRDF`: `Image`-объекты (только bbox, без пикселей) + текст из PDFMiner |
| `extractors/page_extractor/pdf_as_img/` | `PDFIMGExtractor` — рендерит страницы PDF как изображения через `pdf2image` |

**Проблемы:**

1. **OCR-логика живёт в `file_input/`**, а не в extractors. `read_image()` делает и загрузку, и OCR — два разных слоя смешаны.
2. **Нет batch-обработки**: один вызов → все изображения страницы/документа обработаны.
3. **`Image2Words` не пробрасывает confidence** из Tesseract (поле `conf` игнорируется).
4. **Для PDF нет OCR изображений**: `MinerPDFModel` находит изображения (bbox + имя), но не применяет к ним OCR.

## Состав этапа

| № | Секция | Исполнитель | Статус |
|---|--------|-------------|--------|
| 1 | Исследование и ADR (варианты для обсуждения) | researcher + architect | Ожидает |
| 2 | Реализация: перенос tesseract + Images2RegionsExtractor | coder | Ожидает |
| 3 | Тестирование и верификация | coder | Ожидает |

> Секция 4 («Интеграция с FileInput») исключена. `FileInput` и `Images2RegionsExtractor` — независимые компоненты, соединяются пользователем библиотеки. `FileInput` даёт сырой `PageRDF`, `Images2RegionsExtractor` обогащает его OCR.

---

## Ключевые архитектурные решения (ADR)

**Все решения принимаются в процессе обсуждения. Ниже — альтернативы, а не готовые рекомендации.**

### ADR-001: Стратегия извлечения изображений из PDF

**Статус:** Принято. Полный текст решения: [ADR-001](../../adr/001-image-extraction-strategy.md)

**Суть решения:** `Images2RegionsExtractor` — чистый OCR-экстрактор. Он обрабатывает только те `Image`-объекты в `PageRDF`, которые уже содержат пиксельные данные (`data["array"]`). Извлечение пикселей из PDF не входит в его ответственность. За это отвечают другие компоненты (`PDFIMGExtractor` для рендеринга страниц, потенциально — расширение `MinerPDFModel` для встроенных изображений).

---

### ADR-002: Место OCR-логики (Image2Words)

**Статус:** Принято. Полный текст решения: [ADR-002](../../adr/002-ocr-location.md)

**Суть решения:** OCR-логика переносится в `extractors/page_extractor/images2regions/`. Имя пакета следует схеме `<input>2<output>` (`words2rows/`, `rows2regions/`, `images2regions/`). `Image2Words` остаётся отдельным модулем (`image2words.py`) внутри пакета. `file_input/tesseract/__init__.py` реэкспортирует `Image2Words` из нового места для обратной совместимости. `image_read.py` упрощается — только загрузка `Image` без OCR.

---

### ADR-003: Иерархия экстрактора

**Статус:** Принято. Полный текст решения: [ADR-003](../../adr/003-extractor-hierarchy.md)

**Суть решения:** `Images2RegionsExtractor` наследует `BasePageExtractor`. Реализует `page_extract(self, page)` — для каждой страницы находит `Image`-объекты с `data["array"]`, применяет OCR через `Image2Words.get_region()`, добавляет полученные текстовые `Region` в `page.children` рядом с исходными изображениями. Паттерн идентичен существующим page-экстракторам (`Words2Rows`, `Rows2Regions`, `MergeRegion`). `extract()` возвращает `None` (модификация `prdf` in-place), метаданные OCR агрегируются в `prdf.metadata["ocr_info"]` через лёгкое переопределение `extract()` с вызовом `super().extract()`.

---

### ADR-004: Расширение типов данных

**Статус:** Принято. Полный текст решения: [ADR-004](../../adr/004-dtype-extension.md)

**Суть решения:** Confidence слов хранится в `Word.data["confidence"]` (вариант A — без новых классов). Метаданные OCR (время обработки, статистика, конфигурация) **не сохраняются** в `PageRDF` — модель остаётся чистым представлением документа. Результат OCR — один `Region`, собранный из слов (`Region(Row(Word))`), через существующий контракт `Image2Words.get_region()`.

---

## Связанная документация

| Документ | Назначение | Исполнитель |
|----------|------------|-------------|
| `docs/project/research.md` | Ответы на исследовательские вопросы | researcher |
| `docs/adr/001-image-extraction-strategy.md` | ADR-001: стратегия извлечения | architect |
| `docs/adr/002-ocr-location.md` | ADR-002: место Image2Words | architect |
| `docs/adr/003-extractor-hierarchy.md` | ADR-003: иерархия классов | architect |
| `docs/adr/004-dtype-extension.md` | ADR-004: расширение типов | architect |
| `docs/project/api/image_extractor_api.md` | API-спека Images2RegionsExtractor | architect |
| `docs/project/flows/image_extractor_flow.md` | Потоки данных (image + PDF сценарии) | architect |

---

## 1. Исследование и ADR

**Исполнитель:** researcher + architect

### Вход

- Исходный код: `src/pagerlib/file_input/tesseract/`, `src/pagerlib/extractors/`, `src/pagerlib/dtypes/`
- `pyproject.toml` — текущие зависимости
- `visualize_pdf.py` — целевой потребитель результата

### Выход

1. `docs/project/research.md` — исследовательский отчёт
2. `docs/project/adr/00001-image-extraction-strategy.md` — ADR-001
3. `docs/adr/002-ocr-location.md` — ADR-002
4. `docs/project/adr/00003-extractor-hierarchy.md` — ADR-003
5. `docs/adr/004-dtype-extension.md` — ADR-004
6. `docs/project/api/image_extractor_api.md` — API-спека
7. `docs/project/flows/image_extractor_flow.md` — потоки данных

### Задачи

#### Задача 1.1: Исследование (researcher)

**Файлы для анализа:**
- `pyproject.toml`
- `src/pagerlib/file_input/pdf_as_json_model/miner_pdf_model/visual_extractor.py`
- `src/pagerlib/file_input/tesseract/image2words.py`

**Исследовательские вопросы:**

1. **Извлечение пикселей из PDF:** Может ли `pdfminer.six` (`LTImage.stream`) выдать сырые пиксели? Какие форматы встроенных изображений поддерживаются (JPEG, JPEG2000, CCITT, JBIG2, PNG)? Какие форматы декодируются в numpy без внешних библиотек?

2. **pdf2image — ограничения:** Пиковое потребление памяти на PDF из 100 страниц при 150 DPI? Время рендеринга? Можно ли рендерить выборочно (только одну страницу)?

3. **Декодирование LTImage:** Достаточно ли PIL/Pillow для декодирования `LTImage.stream.get_rawdata()`? Нужен ли `pymupdf` (fitz) как альтернатива PDFMiner для извлечения изображений?

4. **Зависимости:** Нужно ли добавлять `pillow` в `pyproject.toml`? `pymupdf`? Достаточно ли существующих?

5. **Метаданные изображений в MinerPDFModel:** Что содержит `page_json['images']`? Есть ли `image_name`, `stream`, `srcsize`? Можно ли восстановить пиксели по этим метаданным без повторного парсинга PDF?

#### Задача 1.2: ADR-001 — Стратегия извлечения изображений из PDF (architect)

**Файл:** `docs/project/adr/00001-image-extraction-strategy.md`  
**Формат:** Контекст → Альтернативы (A/B/C из таблицы выше) → Сравнительный анализ → Рекомендация → Последствия  
**Ссылки:** `visual_extractor.py:189` (process_image), `pdf_as_img.py` (PDFIMGExtractor)

#### Задача 1.3: ADR-002 — Место OCR-логики (architect)

**Файл:** `docs/project/adr/00002-ocr-location.md`  
**Формат:** Контекст → Альтернативы → Рекомендация → План миграции (если перенос) → Последствия  
**Затрагивает:** `file_input/tesseract/image2words.py`, `file_input/tesseract/image_read.py`, будущий `extractors/page_extractor/images2regions/`

#### Задача 1.4: ADR-003 — Иерархия экстрактора (architect)

**Файл:** `docs/project/adr/00003-extractor-hierarchy.md`  
**Формат:** Контекст → Альтернативы → Рекомендация  
**Ссылки:** `base_page_extractor.py`, `base_document_extractor.py`  
**Дополнительный вопрос:** нужно ли изменить контракт базовых классов (возвращать `PageRDF` вместо `None`)?

#### Задача 1.5: ADR-004 — Расширение типов данных (architect)

**Файл:** `docs/adr/004-dtype-extension.md`  
**Формат:** Контекст → Альтернативы → Рекомендация  
**Ссылки:** `pager_doc_format.py`, `word.py`, `row.py`

#### Задача 1.6: API-спека Images2RegionsExtractor (architect)

**Файл:** `docs/project/api/image_extractor_api.md`  
**Ожидаемое содержимое:**
- Конструктор: `Images2RegionsExtractor(conf: dict = None)` — конфигурация Tesseract (lang, psm, oem, resize_factor)
- Основной метод: `extract(prdf: PageRDF) → PageRDF`
- Выходной формат: какие поля добавляются в `prdf.metadata`, `page.children`, `word.data`
- Поведение для image-документов и PDF-документов (после решения ADR-001)

#### Задача 1.7: Потоки данных (architect)

**Файл:** `docs/project/flows/image_extractor_flow.md`  
**Сценарии:**
1. **Одиночное изображение:** `FileInput("img.png")` → `PageRDF` (только `Image`) → `Images2RegionsExtractor.extract()` → `PageRDF` (`Image` + `Region` с OCR-текстом)
2. **PDF:** `FileInput("doc.pdf")` → `PageRDF` (текст PDFMiner + `Image` bbox) → `Images2RegionsExtractor.extract()` → стратегия зависит от ADR-001
3. **Пустой документ:** `PageRDF` без страниц → `extract()` не падает

### Критерии приёмки

- [ ] Все 7 файлов созданы
- [ ] Каждый ADR содержит: контекст, альтернативы (минимум 2), анализ, рекомендацию, последствия
- [ ] API-спека описывает публичный интерфейс без привязки к реализации
- [ ] Потоки данных визуализируют путь данных от FileInput до конечного PageRDF
- [ ] `research.md` отвечает на все 5 вопросов задачи 1.1

### Риски

| Риск | Вероятность | Влияние | Митигация |
|------|------------|---------|-----------|
| PDFMiner не может извлечь пиксели из распространённых форматов | Средняя | Высокое | Выяснить в исследовании до принятия ADR-001 |
| Перенос Image2Words ломает обратную совместимость | Высокая | Среднее | Оставить реэкспорт в `file_input/tesseract/__init__.py` на время миграции |
| Производительность Tesseract на большом PDF | Средняя | Среднее | Измеряется на этапе реализации |

---

## 2. Реализация: перенос tesseract + Images2RegionsExtractor

**Исполнитель:** coder

### Предусловия

- [ ] Все ADR утверждены (секция 1 завершена)
- [ ] `docs/project/api/image_extractor_api.md` существует
- [ ] `docs/project/flows/image_extractor_flow.md` существует

### Вход

- Утверждённые решения ADR-001…004
- API-спека Images2RegionsExtractor
- Потоки данных
- Существующий код

### Выход

- `src/pagerlib/extractors/page_extractor/images2regions/` — новый пакет с OCR-логикой и экстрактором
- `src/pagerlib/file_input/tesseract/image_read.py` — упрощён (только загрузка Image, без OCR)
- Обновлённые импорты

### Задачи

#### Задача 2.1: Перенос Image2Words в extractors

**Исходный файл:** `src/pagerlib/file_input/tesseract/image2words.py`  
**Целевой файл:** `src/pagerlib/extractors/page_extractor/images2regions/image2words.py`

**Действия:**
1. Скопировать `image2words.py` в `extractors/page_extractor/images2regions/`
2. Поправить импорты в скопированном файле: `from pagerlib.dtypes import Image, Region` (было `from pagerlib.dtypes import Image, Region`)
3. Добавить проброс confidence (см. задачу 2.2)
4. В `file_input/tesseract/__init__.py` — оставить совместимость: `from pagerlib.extractors.page_extractor.images2regions.image2words import Image2Words`

**Примечание:** класс `Image2Words` не меняет публичный API. Добавляется только поле `"conf"` в словари слов.

#### Задача 2.2: Модификация Image2Words — проброс confidence

**Файл:** `src/pagerlib/extractors/page_extractor/images2regions/image2words.py`

**Текущая проблема:** `extract_from_img()` в цикле `level == 5` собирает слова из `pytesseract.image_to_data()`, но игнорирует поле `"conf"`.

**Действия:**
1. Сохранить индекс внутри цикла `level == 5`, чтобы получать `tesseract_bboxes["conf"][idx]`
2. В словарь слова добавить: `"conf": float(tesseract_bboxes["conf"][idx])` (или -1 если не распознано)
3. Проверить, что `conf` пробрасывается через всю цепочку:
   - `extract_from_img()` → dict с `"conf"`  
   - `get_region()` → `Region(children=rows)` → `Row._get_children_from_dict_list()` → `Word(data={"text": ..., "confidence": ...})`
4. Сигнатуры `get_region()` и `extract_from_img()` **не менять**

#### Задача 2.3: Упрощение image_read.py

**Файл:** `src/pagerlib/file_input/tesseract/image_read.py`

**Текущее поведение:** загружает файл → `Image2Words` → возвращает `PageRDF` с текстом.

**Новое поведение:** загружает файл → создаёт `PageRDF` только с `Image`-регионом (без OCR).

**После изменений:**
```python
def read_image(method, path):
    if method == 'tesseract':
        tesseract_path = shutil.which("tesseract")
        if tesseract_path is None:
            raise Exception("Tesseract is not installed")
        array = Image.read_img(path)
        image = Image(data={"array": array, "path": str(path)})
        page = Page(children=[image])
        prdf = PageRDF()
        prdf.data["pages"] = [page]
        prdf.metadata["file_type"] = "image"
        return prdf
```

**Важно:** `file_input/tesseract/__init__.py` экспортирует `read_image` — импорт не меняется.

#### Задача 2.4: Расширение Word — свойство confidence

**Файл:** `src/pagerlib/dtypes/physical_elements/word.py`

**Действия:**
1. Добавить property:
   ```python
   @property
   def confidence(self):
       return self.data.get("confidence", None) if self.data else None
   ```
2. Убедиться, что `Row._get_children_from_dict_list()` пробрасывает `data` (уже делает — проверка)
3. Убедиться, что `Word.to_dict()` сериализует `confidence` в `data` (уже — `data` сериализуется как есть)

#### Задача 2.5: Создание класса Images2RegionsExtractor

**Файлы:**
- `src/pagerlib/extractors/page_extractor/images2regions/__init__.py`
- `src/pagerlib/extractors/page_extractor/images2regions/images2regions.py`

**API (определяется в задаче 1.6, здесь — реализация):**

```python
class Images2RegionsExtractor:
    """
    Применяет Tesseract OCR ко всем изображениям в PageRDF.

    Конфигурация:
        lang: str = "eng+rus"
        psm: int = 4
        oem: int = 3
        resize_factor: int = 1
    """

    def __init__(self, conf: dict = None):
        ...

    def extract(self, prdf: PageRDF) -> PageRDF:
        """
        Обходит все страницы, для каждой находит Image-объекты,
        применяет OCR и добавляет текстовые Region в page.children.
        Возвращает модифицированный prdf.
        """
```

**Логика `extract()`:**
```
1. Для каждой страницы в prdf.data["pages"]:
   a. Найти Image-объекты в page.children
   b. Для каждого Image:
      - Если есть data["array"] → Image2Words.get_region(image) → Region с текстом
      - Если нет пикселей (PDF-изображения — только bbox):
        * Вариант A (ADR-001): рендерить всю страницу через pdf2image
        * Вариант B (ADR-001): извлечь пиксели LTImage из PDF
      - Добавить Region в page.children (НЕ заменять существующий Image)
   c. Если Image нет, но page.data["array"] существует (PDFIMGExtractor):
      - Создать Image(data={"array": page.data["array"]})
      - OCR → Region

2. Сохранить метаданные в prdf.metadata["ocr_info"]:
   - extraction_time: float
   - total_images: int
   - tesseract_conf: dict

3. Вернуть prdf
```

**Родительский класс:** зависит от ADR-003.  
Предварительно: самостоятельный класс (не наследует `BaseDocumentExtractor`/`BasePageExtractor`), так как существующие базовые классы возвращают `None`.

#### Задача 2.6: Вспомогательный метод — рендеринг страниц PDF

**Файл:** `src/pagerlib/extractors/page_extractor/images2regions/images2regions.py`

```python
def _render_pdf_page(self, path: str, page_num: int, dpi: int = 150) -> np.ndarray:
    """Рендерит одну страницу PDF в numpy array (RGB)."""
    from pdf2image import convert_from_path
    images = convert_from_path(path, first_page=page_num + 1, last_page=page_num + 1, dpi=dpi)
    return np.array(images[0]) if images else None
```

**Примечание:** реализация зависит от ADR-001. Если выбран вариант B (только встроенные изображения), этот метод не нужен. Если C (гибрид) — нужен как fallback.

#### Задача 2.7: Регистрация в __init__.py

**Файлы:**
- `src/pagerlib/extractors/page_extractor/images2regions/__init__.py` — экспорт `Images2RegionsExtractor`, `Image2Words`
- `src/pagerlib/extractors/page_extractor/__init__.py` — добавить `from .images2regions import Images2RegionsExtractor`

### Критерии приёмки

- [ ] `Image2Words` перенесён в `extractors/page_extractor/images2regions/image2words.py`
- [ ] `Image2Words` пробрасывает confidence в словари слов
- [ ] `image_read.py` возвращает `PageRDF` без OCR-текста (только Image)
- [ ] `Word.confidence` property работает (с confidence и без)
- [ ] `Images2RegionsExtractor.extract(prdf)` дополняет страницы текстовыми Region
- [ ] `prdf.metadata["ocr_info"]` заполняется после успешного extract
- [ ] Существующий `file_input/tesseract/__init__.py` продолжает работать (через реэкспорт)
- [ ] `visualize_pdf.py` запускается без ошибок (не зависит от наших изменений, но проверяем)

### Файлы секции

| Файл | Действие | Описание |
|------|----------|----------|
| `src/pagerlib/extractors/page_extractor/images2regions/__init__.py` | Создать | Экспорт пакета |
| `src/pagerlib/extractors/page_extractor/images2regions/images2regions.py` | Создать | Класс Images2RegionsExtractor |
| `src/pagerlib/extractors/page_extractor/images2regions/image2words.py` | Создать (перенос) | OCR-движок (из file_input) |
| `src/pagerlib/file_input/tesseract/__init__.py` | Изменить | Реэкспорт Image2Words из нового места |
| `src/pagerlib/file_input/tesseract/image_read.py` | Изменить | Упростить — только Image, без OCR |
| `src/pagerlib/dtypes/physical_elements/word.py` | Изменить | Добавить property confidence |
| `docs/project/api/image_extractor_api.md` | Читать | API-спека |
| `docs/project/flows/image_extractor_flow.md` | Читать | Потоки данных |

### Риски

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| Изменение `image_read.py` ломает обратную совместимость | Высокая | Пользователи `FileInput` для изображений больше не получат OCR-текст автоматически. Документировать изменение |
| `pdf2image` требует `poppler-utils` | Высокая | Проверять наличие в `extract()`, выбрасывать понятную ошибку |
| Перенос `image2words.py` дублирует код | Низкая | Оставить реэкспорт в старом месте, удалить старый файл после переходного периода |

---

## 3. Тестирование и верификация

**Исполнитель:** coder

### Предусловия

- [ ] Выполнена секция 2 (реализация завершена)

### Основной критерий приёмки

**Главный тест — пользовательский опыт.** Ключевая утилита `visualize_pdf.py` должна работать. Всё остальное — вторично.

### Задачи

#### Задача 3.1: Верификация visualize_pdf.py

**Файл:** `visualize_pdf.py` (корень проекта, не меняется)

**Действия:**
1. Запустить на тестовом PDF — `tests/all_element/PMC2532955_00002.pdf`
2. Убедиться, что визуализация текстовых строк (синий) и изображений (красный) работает после изменений
3. `visualize_pdf.py` использует `MinerPDFModel` напрямую — изменения в `FileInput`/`Images2RegionsExtractor` не должны на него влиять

#### Задача 3.2: Демо-скрипт использования Images2RegionsExtractor

**Файл:** `examples/image_extractor_demo.py` (создать)

```python
"""Демонстрация: FileInput + Images2RegionsExtractor."""
from pagerlib.file_input import FileInput
from pagerlib.extractors.page_extractor.images2regions import Images2RegionsExtractor

# 1. Загружаем документ (без OCR)
fi = FileInput()
prdf = fi("tests/all_element/PMC2532955_00002.pdf")

# 2. Применяем OCR
extractor = Images2RegionsExtractor()
prdf = extractor.extract(prdf)

# 3. Смотрим результат
print("Pages:", len(prdf.data["pages"]))
print("OCR info:", prdf.metadata.get("ocr_info"))
for i, page in enumerate(prdf.data["pages"]):
    print(f"\nPage {i}:")
    for child in page.children:
        print(f"  {type(child).__name__}: {str(child.text)[:100]}")
```

**Действия:** запустить на 2-3 тестовых PDF, убедиться в корректности вывода.

#### Задача 3.3: Ручная проверка на изображении

**Действия:**
1. Взять любой PNG с текстом (или создать через скрипт)
2. `fi = FileInput()` → `prdf = fi("image.png")` — должен вернуть `PageRDF` с `Image`-регионом без текста
3. `extractor = Images2RegionsExtractor()` → `prdf = extractor.extract(prdf)` — должен добавить `Region` с текстом
4. Проверить, что `word.confidence` заполнен

#### Задача 3.4: Наведение порядка в тестах (отдельная задача)

**Не входит в данный этап.** Создаётся backlog-задача:

> **Этап N: Реорганизация тестов**
> - Актуализировать `tests/all_element/test_all_elements_extraction.py` (может быть сломан после изменений `image_read.py`)
> - Добавить тесты на `Images2RegionsExtractor` (unit + интеграционные)
> - Добавить тесты на `Word.confidence`
> - Добавить тесты на `Image2Words` confidence scores
> - Настроить CI с проверкой наличия tesseract/poppler

### Критерии приёмки

- [ ] `visualize_pdf.py` работает без ошибок на тестовом PDF
- [ ] Демо-скрипт `examples/image_extractor_demo.py` отрабатывает корректно
- [ ] Ручная проверка на изображении: `FileInput` → `Images2RegionsExtractor` даёт текст и confidence
- [ ] Backlog-задача на реорганизацию тестов создана

### Файлы секции

| Файл | Действие | Описание |
|------|----------|----------|
| `examples/image_extractor_demo.py` | Создать | Демо-скрипт |
| `visualize_pdf.py` | Запустить | Верификация |
| `tests/all_element/PMC2532955_00002.pdf` | Использовать | Тестовый PDF |

---

## 4. Взаимодействие FileInput и Images2RegionsExtractor

**Исполнитель:** coder (интеграция не требуется — документирование)

### Концепция

`FileInput` и `Images2RegionsExtractor` — **независимые компоненты**. Пользователь библиотеки сам решает, когда и как их соединять.

```
FileInput("doc.pdf")           → PageRDF (текст PDFMiner + Image bbox)
FileInput("img.png")           → PageRDF (только Image, без текста)

Images2RegionsExtractor().extract(prdf) → PageRDF (добавлены Region с OCR-текстом)
```

**Никакой магии в `FileInput.__init__` не добавляется.** Никаких `use_image_extractor=True`. Библиотека предоставляет кирпичики, пользователь строит pipeline.

### Что делает FileInput (после изменений)

| Формат | Метод | Результат |
|--------|-------|-----------|
| `.pdf` | `pdf_reader()` | `PageRDF`: текст PDFMiner в `Region`, изображения в `Image` (только bbox, без пикселей) |
| `.jpg`, `.jpeg`, `.png` | `image_reader()` | `PageRDF`: `Image` с пиксельным массивом (`data["array"]`), без текста |

Ключевое изменение: `image_reader()` больше не делает OCR. Возвращает документ «как есть» — одну страницу с одним `Image`-регионом.

### Что делает Images2RegionsExtractor

| Вход | Стратегия | Результат |
|------|-----------|-----------|
| `PageRDF` от изображения | `Image2Words` на `Image.img` | Добавлен `Region` с текстом в `page.children` |
| `PageRDF` от PDF | Зависит от ADR-001 (рендеринг страниц или извлечение `LTImage`) | Добавлены `Region` с OCR-текстом |

### Типичный пользовательский код

```python
from pagerlib.file_input import FileInput
from pagerlib.extractors.page_extractor.images2regions import Images2RegionsExtractor

# Загрузка
fi = FileInput()
prdf = fi("document.pdf")       # или "scan.png"

# OCR (опционально — только если нужен)
extractor = Images2RegionsExtractor(conf={"lang": "eng", "psm": 4})
prdf = extractor.extract(prdf)

# Результат
for page in prdf.data["pages"]:
    for child in page.children:
        if hasattr(child, 'confidence'):
            print(f"  {child.text}  ({child.confidence:.0f}%)")
```

### Что менять в FileInput

**Минимальные изменения для консистентности:**

1. `image_reader()` — упростить (задача 2.3)
2. `pdf_reader()` — добавить `prdf.metadata["file_type"] = "pdf"` (уже можно, но не обязательно — `Images2RegionsExtractor` может определять тип по структуре `PageRDF`)

**Никаких новых параметров в `FileInput.__init__`.** Библиотека = строительные блоки.

### Критерии приёмки

- [ ] `FileInput("img.png")` возвращает `PageRDF` без OCR-текста (только `Image`-регион)
- [ ] `FileInput("doc.pdf")` работает как раньше (текст PDFMiner + Image bbox)
- [ ] `Images2RegionsExtractor().extract(prdf)` дополняет изображения текстом
- [ ] Пользователь может использовать компоненты независимо
- [ ] `image_reader()` и `pdf_reader()` продолжают работать как публичные методы

### Риски

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| Пользователи ожидают, что `FileInput` сразу даёт OCR-текст | Высокая | Документировать изменение. В ридми показать новый способ: `FileInput` + `Images2RegionsExtractor` |
| `FileInput.__init__` принимает `*args` — неочевидный API | Средняя | Не менять в этом этапе. Отдельная задача на рефакторинг `FileInput` |

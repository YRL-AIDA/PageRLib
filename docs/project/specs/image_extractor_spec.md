# Спецификация: Image Extractor для Tesseract OCR

**Версия:** 1.0-draft  
**Дата:** 2026-07-16  
**Статус:** Проект  
**Зависимости:** pytesseract, pdf2image, numpy, opencv-python, pdfminer.six

---

## 1. Назначение

`Images2RegionsExtractor` — экстрактор, который принимает на вход документ (файл изображения или PDF), обходит **все изображения** в документе и применяет Tesseract OCR к каждому. Возвращает структурированный результат: текст с координатами bounding box, confidence scores и метаданные.

### Отличие от существующего кода

| Существующий код | Новый Images2RegionsExtractor |
|-----------------|---------------------|
| `read_image()` — 1 изображение → 1 `PageRDF` | Документ (N страниц) → 1 `PageRDF` с N обработанных страниц |
| `Image2Words` — применяется вручную к одному `Image` | Автоматический обход всех изображений |
| `FileInput` — роутинг PDF/IMG, без OCR для PDF-изображений | OCR применяется ко всем изображениям, включая PDF |
| Нет confidence scores | Confidence из Tesseract сохраняется в `Word.data["confidence"]` |

---

## 2. API

### 2.1 Класс `Images2RegionsExtractor`

```python
class Images2RegionsExtractor(BaseDocumentExtractor):
    """Экстрактор изображений с Tesseract OCR.

    Обходит все изображения документа и применяет OCR к каждому.
    Наследует BaseDocumentExtractor.

    Параметры конфигурации (conf: dict):
        lang (str):           Языки Tesseract, по умолчанию "eng+rus"
        psm (int):            Page Segmentation Mode, по умолчанию 4
        oem (int):            OCR Engine Mode, по умолчанию 3
        resize_factor (int):  Множитель разрешения для Tesseract, по умолчанию 1
        page_images_mode (bool):    Рендерить страницы PDF как изображения
        embedded_images_mode (bool): Извлекать встроенные изображения PDF
        dpi (int):                  DPI для рендеринга PDF страниц, по умолчанию 200
    """

    def __init__(self, conf: dict = None):
        """Инициализация с конфигурацией Tesseract."""

    def document_extract(self, prdf: PageRDF) -> dict:
        """Извлекает OCR-текст из всех изображений документа.

        Returns:
            dict с результатами для prdf.metadata["ocr_info"]:
                - extraction_time: float
                - total_images: int
                - tesseract_conf: dict
                - page_results: list[dict]
        """

    def extract(self, prdf: PageRDF) -> PageRDF:
        """Основной публичный метод.

        Принимает PageRDF с заполненными pages (Image-объекты с pixel array).
        Для каждой страницы применяет OCR, добавляет Region с текстом.
        Сохраняет метаданные в prdf.metadata["ocr_info"].

        Returns:
            Тот же объект PageRDF, модифицированный in-place.
        """
```

### 2.2 Сигнатуры существующих модифицируемых функций

```python
# src/pagerlib/file_input/tesseract/image2words.py

class Image2Words:
    def __init__(self, conf=None):
        """Без изменений."""

    def get_region(self, image: Image) -> Region:
        """Без изменений в сигнатуре.
        Внутри: Word создаётся с data={"text": ..., "confidence": float}."""

    def extract_from_img(self, img: np.ndarray) -> list[dict]:
        """Без изменений в сигнатуре.
        Внутри: каждый word-dict получает ключ "conf" (float)."""

# src/pagerlib/dtypes/physical_elements/word.py

class Word(PhysicalElement):
    def __init__(self, segment=None, data=None, **kwargs):
        """Без изменений в сигнатуре.
        data может содержать ключ "confidence": float."""

    @property
    def confidence(self) -> float | None:
        """Уверенность OCR (0..100) или None."""
```

### 2.3 Модифицированный `FileInput`

```python
# src/pagerlib/file_input/file_input.py

class FileInput:
    def __init__(self, *args):
        """
        Принимает позиционные аргументы:
            "image_method": str = "tesseract"
            "pdf_method": str = "miner"
            "use_image_extractor": bool = False      # NEW
            "image_extractor_conf": dict = None       # NEW
        """

    def __call__(self, path: Path | str) -> PageRDF:
        """
        Если use_image_extractor=True:
            после базового чтения вызывает Images2RegionsExtractor.extract(prdf).
        """
```

---

## 3. Типы данных

### 3.1 `PageRDF` (существующий, расширен)

```python
class PageRDF:
    base_type: str | None
    data: Dict
        # Существующие ключи:
        "pages": list[Page]      # Список страниц
        "path": str              # Путь к исходному файлу

    metadata: Dict
        # Существующие ключи: (нет обязательных)
        # Новые ключи (добавляются Images2RegionsExtractor):
        "file_type": str              # "pdf" | "image"
        "ocr_info": {                 # Добавляется Images2RegionsExtractor
            "extraction_time": float, # Время выполнения OCR (сек)
            "total_images": int,      # Всего обработано изображений
            "tesseract_conf": {       # Использованная конфигурация
                "lang": str,
                "psm": int,
                "oem": int,
                "resize_factor": int,
            },
            "page_results": [         # Постраничная статистика
                {
                    "page_num": int,
                    "num_images": int,
                    "text_length": int,
                    "avg_confidence": float | None,
                },
                ...
            ]
        }
```

### 3.2 `Word` (существующий, расширен)

```python
class Word(PhysicalElement):
    segment: ImageSegment
    data: Dict
        # Существующие ключи:
        "text": str              # Текст слова
        "font": dict             # Информация о шрифте (опционально)

        # Новый ключ:
        "confidence": float      # Уверенность OCR от Tesseract (0..100)
                                 # Может отсутствовать для не-OCR слов

    children: None               # Word — листовой элемент

    @property
    def text(self) -> str: ...
    @property
    def confidence(self) -> float | None: ...  # NEW
```

### 3.3 Иерархия элементов (существующая, без изменений структуры)

```
PageRDF
└── data["pages"]: list[Page]
    └── Page.children: list[Region | Image]
        ├── Image                      # Исходное изображение
        │   └── data["array"]: np.ndarray
        │       data["path"]: str
        │
        └── Region (результат OCR)     # ← добавляется Images2RegionsExtractor
            └── children: list[Row]
                └── Row.children: list[Word]
                    └── Word.data:
                        ├── "text": str
                        └── "confidence": float  # ← новое поле
```

---

## 4. Потоки данных

### 4.1 Сценарий: Одиночное изображение

```
path: "photo.png"
  │
  ▼
FileInput.__call__()
  │
  ├─ image_reader("photo.png")
  │   └─ read_image("tesseract", "photo.png")
  │       ├─ Image.read_img("photo.png") → np.ndarray (RGB)
  │       ├─ Image(data={"array": arr, "path": "photo.png"})
  │       ├─ Image2Words.get_region(image) → Region(Row(Word))
  │       └─ Page(children=[Image, Region]) → PageRDF
  │
  └─ [if use_image_extractor]
     └─ Images2RegionsExtractor.extract(prdf)
        ├─ Для page.children: ищем Image с array
        ├─ Image2Words.get_region(image) → Region
        ├─ Добавляем Region в page.children
        └─ prdf.metadata["ocr_info"] = {...}
```

### 4.2 Сценарий: PDF (рендеринг страниц)

```
path: "document.pdf"
  │
  ▼
FileInput.__call__()
  │
  ├─ pdf_reader("document.pdf")
  │   └─ MinerPDFModel.read_from_file()
  │       └─ PDFStructureExtractor.extract_from_path()
  │           └─ page_json = {rows: [...], images: [...], height, width}
  │   └─ Для каждой страницы:
  │       ├─ Image (из page_json["images"]) — без pixel array
  │       └─ Region (из page_json["rows"])  — текст из PDF
  │   └─ PageRDF(pages=[Page, ...])
  │
  └─ [if use_image_extractor]
     └─ Images2RegionsExtractor.extract(prdf)
        ├─ prdf.metadata["file_type"] == "pdf"
        ├─ Если page_images_mode:
        │   ├─ pdf2image.convert_from_path(path, dpi=200)
        │   │   → List[PIL.Image]  (по одной на страницу)
        │   └─ Для каждой страницы:
        │       ├─ pil → np.ndarray (RGB)
        │       ├─ image = Image(data={"array": arr})
        │       ├─ Image2Words.get_region(image) → Region(Row(Word))
        │       └─ page.children.append(region)
        │
        ├─ Если embedded_images_mode:
        │   └─ _extract_embedded_images(path)
        │       └─ Для каждого LTImage: декодировать stream → np.ndarray
        │       └─ Image2Words для каждого → результаты
        │
        └─ prdf.metadata["ocr_info"] = {
            extraction_time, total_images, tesseract_conf, page_results
           }
```

### 4.3 Сценарий: PDF без Images2RegionsExtractor (обратная совместимость)

```
FileInput(use_image_extractor=False)  # по умолчанию
  │
  ├─ pdf_reader() → MinerPDFModel → PageRDF (текст PDF)
  ├─ image_reader() → read_image() → PageRDF (OCR одного изображения)
  │
  └─ Результат без ocr_info, без дополнительных Region
```

---

## 5. Конфигурация Tesseract

### Параметры по умолчанию

| Параметр | Значение | Описание |
|----------|----------|----------|
| `lang` | `"eng+rus"` | Языки распознавания |
| `psm` | `4` | Page Segmentation Mode: «Assume a single column of text of variable sizes» |
| `oem` | `3` | OCR Engine Mode: «Default, based on what is available» |
| `resize_factor` | `1` | Множитель разрешения (k=2 → изображение увеличено вдвое перед OCR) |

### Возможные значения PSM

| PSM | Описание |
|-----|----------|
| 3 | Fully automatic page segmentation (default) |
| 4 | Assume a single column of text of variable sizes |
| 6 | Assume a uniform block of text |
| 11 | Sparse text. Find as much text as possible in no particular order |
| 12 | Sparse text with OSD |

### Возможные значения OEM

| OEM | Описание |
|-----|----------|
| 0 | Legacy engine only |
| 1 | Neural nets LSTM engine only |
| 2 | Legacy + LSTM engines |
| 3 | Default, based on what is available |

---

## 6. Требования к окружению

### Системные зависимости

| Зависимость | Назначение | Проверка |
|------------|-----------|----------|
| `tesseract-ocr` | Движок OCR | `shutil.which("tesseract")` |
| `tesseract-ocr-eng` | Английский языковой пакет | Файлы в `tessdata/` |
| `tesseract-ocr-rus` | Русский языковой пакет | Файлы в `tessdata/` |
| `poppler-utils` | Рендеринг PDF страниц (для pdf2image) | `shutil.which("pdftoppm")` |

### Python-зависимости (все уже в pyproject.toml)

```
pytesseract>=0.3.10
pdf2image>=1.16.0
numpy>=1.21.0
opencv-python>=4.5.0
```

---

## 7. Обработка ошибок

| Ситуация | Поведение |
|----------|-----------|
| Tesseract не установлен | `RuntimeError("Tesseract is not installed. Install: apt install tesseract-ocr")` |
| Poppler не установлен (для PDF) | `RuntimeError("poppler-utils is required for PDF processing. Install: apt install poppler-utils")` |
| Файл не существует | `FileNotFoundError` (пробрасывается из `FileInput`) |
| PDF без страниц | Возвращается пустой `PageRDF` с `ocr_info.total_images = 0` |
| Изображение без массива (`Image.data["array"]` is None) | Пропускается с warning |
| Tesseract вернул пустой результат | `Region` без `Row`-детей (валидный пустой результат) |
| Встроенное изображение PDF не может быть декодировано | Warning, изображение пропускается |

---

## 8. Ограничения и не-цели (v1)

- **Не поддерживается:** параллельная обработка страниц (будущая оптимизация)
- **Не поддерживается:** извлечение встроенных изображений PDF через PDFMiner stream (v1 — только рендеринг страниц; v2 — embedded images mode)
- **Не поддерживается:** DOCX и другие форматы (только PDF + изображения)
- **Не поддерживается:** предобработка изображений (deskew, denoise) — можно добавить позже через параметры конфигурации
- **Не поддерживается:** GPU-ускорение Tesseract (требует сборки из исходников)

---

## 9. Связанные документы

| Документ | Путь |
|----------|------|
| Глобальный план | `docs/plan/global.md` |
| Спецификация этапа 1 | `docs/plan/00001-image-extractor-spec.md` |
| Спецификация этапа 2 | `docs/plan/00002-image-extractor-impl.md` |
| Спецификация этапа 3 | `docs/plan/00003-image-extractor-tests.md` |
| Спецификация этапа 4 | `docs/plan/00004-image-extractor-integration.md` |
| API-спека (architect) | `docs/project/api/image_extractor_api.md` |
| Модели данных (architect) | `docs/project/models/image_extractor_models.md` |
| Потоки данных (architect) | `docs/project/flows/image_extractor_flow.md` |
| ADR (architect) | `docs/project/adr/` |
| Исследование (researcher) | `docs/project/research.md` |

# ADR-002: Место OCR-логики (Image2Words + Images2RegionsExtractor)

**Дата:** 2026-07-16
**Статус:** Принято
**План:** [00001-image-extractor.md](../plan/00001-image-extractor.md)

---

## Контекст

Сейчас OCR-логика живёт в `src/pagerlib/file_input/tesseract/`:
- `image2words.py` — класс `Image2Words`, OCR-движок на базе Tesseract
- `image_read.py` — `read_image()`, загрузка изображения + OCR (два слоя смешаны)

Это нарушает принцип разделения ответственности: `file_input/` должен только загружать документы, а OCR — это обработка (зона ответственности `extractors/`).

Нужно решить, куда перенести:
1. `Image2Words` — низкоуровневый OCR-движок (обёртка над `pytesseract`)
2. `Images2RegionsExtractor` — batch-экстрактор, обходит все `Image`-объекты в `PageRDF` и применяет OCR

## Ключевые архитектурные принципы

1. **Единообразие структуры.** Экстракторы в проекте размещаются в `extractors/page_extractor/` с поддиректориями по схеме `<input>2<output>/` (например, `words2rows/`, `rows2regions/`). `pdf_as_img/` — исключение (не по схеме `<X>2<Y>`), но сохранено для обратной совместимости.
2. **Разделение слоёв.** `file_input/` = загрузка «как есть». `extractors/` = обработка. OCR-движок — часть обработки.
3. **Минимальная вложенность.** Экстрактор не должен создавать лишние уровни иерархии пакетов.

## Альтернативы

| Вариант | Путь | Плюсы | Минусы |
|---------|------|-------|--------|
| **A. `extractors/image_extractor/`** | `extractors/image_extractor/images2regions.py` + `image2words.py` | Отдельный пакет для image-экстракторов, можно наращивать | Ломает единообразие: единственный экстрактор не в `page_extractor/`. Создаёт третий подпакет в `extractors/` наравне с `page_extractor/` и `document_extractor/` |
| **B. `page_extractor/images2regions/`** | `page_extractor/images2regions/images2regions.py` + `image2words.py` | Единообразие: все page-экстракторы в одном месте. Имя `images2regions` следует схеме `<input>2<output>`. `Images2RegionsExtractor` — логически page-экстрактор (работает постранично) | — |
| **C. Встроить в `Images2RegionsExtractor`** | `page_extractor/images2regions/images2regions.py` (без отдельного `image2words.py`) | Нет лишнего модуля, всё в одном классе | `Image2Words` может быть полезен отдельно (быстрый OCR одного изображения без `PageRDF`). Дублирование если кому-то понадобится отдельно |

## Решение

**Принят вариант B — `extractors/page_extractor/images2regions/`.**

Структура пакета:

```
extractors/page_extractor/images2regions/
├── __init__.py              # Экспорт: Images2RegionsExtractor, Image2Words
├── images2regions.py        # Класс Images2RegionsExtractor(BasePageExtractor)
└── image2words.py           # Класс Image2Words (перенесён из file_input/tesseract/)
```

### Обоснование

1. **Следует существующей схеме именования.** `words2rows/` (Words → Rows), `rows2regions/` (Rows → Regions), `images2regions/` (Images → Regions). Название ясно отражает суть: на входе изображения, на выходе текстовые регионы.

2. **Логически это page-экстрактор.** `Images2RegionsExtractor` наследует `BasePageExtractor`, обрабатывает страницы по одной. Ему место среди других page-экстракторов.

3. **`image2words.py` остаётся отдельным модулем.** `Image2Words` — переиспользуемый OCR-движок. Его можно использовать напрямую (OCR одного изображения без `PageRDF`), поэтому он вынесен в отдельный файл, а не встроен в класс экстрактора.

4. **Расширяемость.** Если в будущем появятся другие image-экстракторы (например, `Image2Tables`), они могут быть добавлены в поддиректорию `page_extractor/images2regions/` или в соседнюю `page_extractor/images2tables/`.

### Что остаётся в `file_input/tesseract/`

- `__init__.py` — реэкспорт `Image2Words` из нового места для обратной совместимости: `from pagerlib.extractors.page_extractor.images2regions.image2words import Image2Words`
- `image_read.py` — упрощается: загрузка → `Image` с `data["array"]` → `PageRDF` без OCR
- `image2words.py` — **удаляется** (перенесён, реэкспорт идёт из `__init__.py`)

## Последствия

### Положительные

- Все page-экстракторы в одной директории `extractors/page_extractor/`. Легко найти, легко понять архитектуру.
- Имя `images2regions` самодокументируемо: понятно, что делает экстрактор.
- `Image2Words` доступен и как часть экстрактора, и как отдельный утилитный класс.

### Отрицательные

- Изменение путей импорта ломает код, который импортирует `Image2Words` напрямую из `file_input.tesseract.image2words`. Митигируется реэкспортом в `file_input/tesseract/__init__.py`.
- `image_read.py` теряет OCR-возможности — пользователи `FileInput` для изображений больше не получат OCR-текст автоматически. Документируется как осознанное изменение архитектуры: загрузка ≠ обработка.

### Требующиеся изменения

1. Создать `extractors/page_extractor/images2regions/` с `__init__.py`, `images2regions.py`, `image2words.py`
2. `image2words.py` — скопировать из `file_input/tesseract/`, добавить проброс confidence
3. `images2regions.py` — новый класс `Images2RegionsExtractor(BasePageExtractor)`
4. `image_read.py` — упростить до загрузки без OCR
5. `file_input/tesseract/__init__.py` — реэкспорт `Image2Words` из нового места
6. `file_input/tesseract/image2words.py` — удалить
7. `extractors/page_extractor/__init__.py` — добавить экспорт `Images2RegionsExtractor`

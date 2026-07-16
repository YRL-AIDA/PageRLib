# ADR-003: Иерархия экстрактора — выбор родительского класса для Images2RegionsExtractor

**Дата:** 2026-07-16
**Статус:** Принято
**План:** [00001-image-extractor.md](../plan/00001-image-extractor.md)

---

## Контекст

`Images2RegionsExtractor` — новый экстрактор, который обходит все страницы `PageRDF`, находит `Image`-объекты с пиксельными данными (`data["array"]`) и применяет к ним Tesseract OCR. Результат — текстовые `Region` с confidence scores, добавленные в `page.children` рядом с исходными `Image`.

Нужно выбрать родительский класс. В проекте существуют два базовых класса:

| Базовый класс | Контракт | Поведение `extract()` |
|---------------|----------|-----------------------|
| `BasePageExtractor` | `page_extract(self, page)` — обработка одной страницы | Итерирует `prdf.data["pages"]`, вызывает `page_extract(page)`, затем `sorter(page)`. Возвращает `None` (модифицирует `prdf` in-place) |
| `BaseDocumentExtractor` | `document_extract(self, prdf) → dict` — обработка всего документа | Вызывает `document_extract(prdf)`, сохраняет результат в `prdf.data["toc"]`. Возвращает `None` |

## Ключевые архитектурные принципы

1. **Page-level семантика.** `Images2RegionsExtractor` работает постранично: для каждой страницы находит изображения → OCR → добавляет `Region` в `page.children`. Это соответствует паттерну page-экстрактора.
2. **Следование существующему паттерну.** Все экстракторы в `page_extractor/` (`Words2Rows`, `Rows2Regions`, `MergeRegion`, `FontEmbExtractor`, `PDFIMGExtractor`) наследуют `BasePageExtractor` и реализуют `page_extract(page)`, модифицируя `page.children` in-place.
3. **Сортировка.** `BasePageExtractor.extract()` автоматически сортирует children страницы через `RegionSorterCutXYExtractor` после каждого вызова `page_extract()` — это нужно и для `Images2RegionsExtractor`, чтобы OCR-регионы были отсортированы вместе с остальными элементами.

## Альтернативы

| Вариант | Родитель | Описание |
|---------|----------|----------|
| **A. BasePageExtractor** | `page_extract(page)` — постраничная обработка | Для каждой страницы: найти `Image` с `data["array"]`, OCR → `Region`, добавить в `page.children`. Модификация in-place. |
| **B. BaseDocumentExtractor** | `document_extract(prdf) → dict` — обработка всего документа | Обработать все страницы за один вызов, вернуть словарь с метаданными OCR. Результат попадает в `prdf.data["toc"]`. |
| **C. Самостоятельный** | Без наследования, свой метод `extract(prdf) → PageRDF` | Полный контроль над сигнатурой и возвращаемым значением. |

### Анализ

**Вариант A (BasePageExtractor):**

Плюсы:
- Единообразие: все page-экстракторы следуют одному паттерну. Новый разработчик, знакомый с `Words2Rows` или `Rows2Regions`, сразу поймёт `Images2RegionsExtractor`.
- Автоматическая сортировка: `sorter(page)` вызывается после `page_extract`, что гарантирует правильный пространственный порядок `page.children` после добавления OCR-регионов.
- Семантически верно: добавление текстового `Region` к `Image` в `page.children` — это page-level операция, как и остальные page-экстракторы.
- Минимальный код: не нужно переопределять `extract()`, не нужно дублировать цикл по страницам и вызов сортировщика.

Минусы:
- `extract()` возвращает `None`, а не `PageRDF`. Но это консистентно со всеми остальными экстракторами — они модифицируют `prdf` in-place. Пользователь пишет `extractor.extract(prdf)` и дальше работает с тем же объектом `prdf`.
- Нельзя вернуть новый `PageRDF` (иммутабельный паттерн). Но весь проект использует мутабельный подход — изменение `prdf` in-place.

**Вариант B (BaseDocumentExtractor):**

Плюсы:
- Доступ ко всему документу за один вызов `document_extract(prdf)`.
- Может агрегировать статистику по всем страницам (total_images, avg_confidence).

Минусы:
- Результат `document_extract` сохраняется в `prdf.data["toc"]` — это семантически неверно для OCR-метаданных. `toc` (table of contents) предназначен для структуры документа, а не для статистики обработки.
- Ломает единообразие: все экстракторы в `page_extractor/` наследуют `BasePageExtractor`. `Images2RegionsExtractor` в `page_extractor/` с родителем `BaseDocumentExtractor` — путаница.
- Пришлось бы переопределять `extract()`, чтобы не писать результат в `toc`, что сводит на нет смысл наследования.
- Противоречит принятому ADR-002, где `Images2RegionsExtractor` явно помещён в `page_extractor/images2regions/`.

**Вариант C (Самостоятельный):**

Плюсы:
- Полный контроль над API: можно сделать `extract(prdf) → PageRDF` с явным возвратом.

Минусы:
- Дублирование кода: свой цикл по страницам, свой вызов сортировщика.
- Отход от паттернов проекта без веской причины.
- Разработчику придётся помнить, что этот экстрактор «особенный» — не как все остальные.

## Решение

**Принят вариант A — наследование от `BasePageExtractor`.**

### Обоснование

1. **Page-level семантика.** `Images2RegionsExtractor` обрабатывает страницы по одной: для каждой страницы находит изображения и добавляет OCR-регионы в `page.children`. Это чистый page-экстрактор.

2. **Следование паттерну.** Все существующие page-экстракторы (`Words2Rows`, `Rows2Regions`, `MergeRegion`, `FontEmbExtractor`, `PDFIMGExtractor`) построены по одной схеме:
   ```python
   class SomeExtractor(BasePageExtractor):
       def page_extract(self, page):
           # Разделить page.children на целевые и нет
           # Обработать целевые
           # page.children = нецелевые + результат обработки
   ```
   `Images2RegionsExtractor` естественно вписывается в эту схему.

3. **Сортировка из коробки.** `BasePageExtractor.extract()` автоматически вызывает `sorter(page)` после `page_extract()`. Это гарантирует, что добавленные OCR-регионы будут правильно отсортированы по координатам на странице.

4. **Возврат `None` — не проблема, а консистентность.** Все экстракторы проекта модифицируют `PageRDF` in-place. Пользовательский код выглядит одинаково для любого экстрактора:
   ```python
   extractor.extract(prdf)
   # prdf уже изменён, работаем с ним дальше
   ```

### Реализация `page_extract`

```python
class Images2RegionsExtractor(BasePageExtractor):
    def page_extract(self, page: Page):
        images = [child for child in page.children if isinstance(child, Image)]
        non_images = [child for child in page.children if not isinstance(child, Image)]
        
        new_regions = []
        for image in images:
            if image.data and image.data.get("array") is not None:
                region = self.image2words.get_region(image)
                new_regions.append(region)
        
        page.children = non_images + new_regions
```

Паттерн полностью идентичен существующим экстракторам:
- `Words2Rows`: `page.children = no_text_regions + [Region(children=row_list)]`
- `Rows2Regions`: `page.children = no_text_regions + region_list`
- `Images2RegionsExtractor`: `page.children = non_images + new_regions`

### Метаданные OCR

`prdf.metadata["ocr_info"]` заполняется не в `page_extract()` (он работает с одной страницей), а путём переопределения `extract()` с вызовом `super().extract()` и добавлением агрегированной статистики после обработки всех страниц:

```python
def extract(self, prdf: PageRDF):
    start = time.time()
    super().extract(prdf)  # page_extract для каждой страницы + сортировка
    prdf.metadata["ocr_info"] = {
        "extraction_time": time.time() - start,
        "total_images": self._count_images(prdf),
        "tesseract_conf": self.conf,
    }
```

Это единственное отступление от базового класса — агрегация метаданных после постраничной обработки. Сам `page_extract` остаётся чистым и тестируемым.

## Последствия

### Положительные

- **Единообразие.** `Images2RegionsExtractor` следует тому же паттерну, что и 5 других page-экстракторов. Кодовая база предсказуема.
- **Автоматическая сортировка.** `sorter(page)` гарантирует правильный порядок children после добавления OCR-регионов.
- **Минимальный код.** Не нужно писать цикл по страницам и вызов сортировщика — это даёт базовый класс.
- **Тестируемость.** `page_extract(page)` можно тестировать изолированно на одной странице, без создания полного `PageRDF`.

### Отрицательные

- `extract()` возвращает `None` — пользователь должен знать, что `prdf` модифицируется in-place. Но это консистентно со всеми остальными экстракторами проекта.
- Для агрегации метаданных (`ocr_info`) требуется небольшое переопределение `extract()` с вызовом `super().extract()`.

### Требующиеся изменения

- `Images2RegionsExtractor` наследует `BasePageExtractor`
- Реализует `page_extract(self, page)` по паттерну: разделение children → обработка Image → переприсваивание `page.children`
- Переопределяет `extract(self, prdf)` для агрегации `ocr_info` в `prdf.metadata`
- Спецификация `docs/project/specs/image_extractor_spec.md` подлежит обновлению: заменить `BaseDocumentExtractor` на `BasePageExtractor` в описании API (п. 2.1)

# Глобальный план: PageRLib

**Дата создания:** 2026-07-16
**Дата ревизии:** 2026-10-16
**Статус:** В работе
**Цель:** Библиотека для конвертации неструктурированных документов (PDF, изображения) в структурированные данные.

---

## Архитектура проекта

```
src/pagerlib/
├── dtypes/          # Типы данных: PageRDF, Page, Region, Row, Word, Image, Section, Context
├── extractors/      # Экстракторы: page_extractor/, document_extractor/
│   ├── page_extractor/     # Постраничные: Rows2Regions, Words2Rows, MergeRegion, PDFIMGExtractor, FontEmbExtractor, Images2RegionsExtractor
│   │   └── images2regions/ # OCR-обработка изображений: Images2RegionsExtractor, Image2Words (← перенесён из file_input)
│   └── document_extractor/ # Документные: BaseDocumentExtractor, LogicalStructureExtractor
├── file_input/      # Загрузка документов: FileInput, PDF-модели (MinerPDFModel). Без OCR.
├── output/          # Вывод (заглушка)
└── utils/           # Утилиты
```

---

## Завершённые этапы

| № | Этап | Результат |
|---|------|-----------|
| — | Типы данных (`dtypes/`) | `PageRDF`, `Page`, `Region`, `Row`, `Word`, `Image`, `ImageSegment` |
| — | PDF-экстрактор (`miner_pdf_model/`) | `MinerPDFModel` — извлечение текста, изображений, шрифтов из PDF через `pdfminer.six` |
| — | Tesseract OCR (`file_input/tesseract/`) | `Image2Words` — OCR одного изображения. `read_image()` — загрузка изображения как документа (без OCR-текста, только Image-регион) |
| — | FileInput (`file_input/file_input.py`) | Роутинг: PDF → MinerPDFModel, изображения → `read_image()` |
| — | Page extractors (`extractors/page_extractor/`) | `Rows2Regions`, `Words2Rows`, `MergeRegion`, `PDFIMGExtractor`, `FontEmbExtractor` |
| — | Document extractors (`extractors/document_extractor/`) | `BaseDocumentExtractor`, `LogicalStructureExtractor` |
| — | Перенос OCR в extractors | `Image2Words` перемещён в `extractors/page_extractor/images2regions/`, `file_input/tesseract/` оставлен с реэкспортом для совместимости |
| 2 | **Word schema uniform** — единая схема слова (PDF/OCR), устранение KeyError 'font' в Rows2Regions | ADR-005 принят; фикс `rows2regions.py` (вариант A) + дефект `Font({})` в `font.py`; регресс-тесты `tests/words_schema/test_word_schema_uniform.py` 13/13 и `tests/all_element/test_all_elements_extraction.py` 7/7 прошли; спеки (`data_types_spec`, `page_extractors_spec`, `file_input_spec`) обновлены и согласованы documenter'ом — [00002-words-schema-uniform.md](./00002-words-schema-uniform.md) |

---

## Текущие этапы

| № | Этап | Документ | Статус |
|---|------|----------|--------|
| 1 | **Image Extractor** — batch-OCR всех изображений документа | [00001-image-extractor.md](./00001-image-extractor.md) | ADR-001, ADR-002 приняты |

---

## Будущие этапы (бэклог)

| № | Этап | Описание |
|---|------|----------|
| 3 | Устранение pre-existing расхождений документации (не входили в этап 2; код не трогать; зона: architect/documenter) | `docs/project/specs/page_extractors_spec.md` §2.3/§6: `CLASSES[3]` описан как `'text'` (дубль класса 1) — в коде `src/pagerlib/extractors/page_extractor/rows2regions/rows2regions.py:9` это `3: 'list'`; §2.3 (стр. ~206): описание «page.children = no_text_regions + region_list» — код делает `page.children = region_list` (`no_text_regions` не используется); §3.1: устарел токенизатор `rowsGLAM_tokenizer_20260225`, активен `20260826` (alias FontEmbRowGLAMTokenizer), устарели таблица признаков узлов и «pdf_img зарезервирован»; `docs/project/models/data_types_spec.md` §2.4/§4.7: добавить `list` в перечень допустимых `label`; `docs/project/flows/file_input_spec.md` §12: мёртвые ссылки на `docs/project/api/` и `docs/project/adr/` (ADR лежат в `docs/adr/`). |

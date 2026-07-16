# Глобальный план: PageRLib

**Дата создания:** 2026-07-16
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

---

## Текущие этапы

| № | Этап | Документ | Статус |
|---|------|----------|--------|
| 1 | **Image Extractor** — batch-OCR всех изображений документа | [00001-image-extractor.md](./00001-image-extractor.md) | ADR-001, ADR-002 приняты |

---

## Будущие этапы (бэклог)

| № | Этап | Описание |
|---|------|----------|

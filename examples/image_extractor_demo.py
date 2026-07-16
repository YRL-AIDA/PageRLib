"""Демонстрация: FileInput + Images2RegionsExtractor."""
import sys
from pathlib import Path

from pagerlib.file_input import FileInput
from pagerlib.extractors.page_extractor.images2regions import Images2RegionsExtractor


def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/image_extractor_demo.py <path_to_image_or_pdf>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    # 1. Загружаем документ (без OCR)
    fi = FileInput()
    prdf = fi(path)
    print(f"Loaded: {path}")
    print(f"  File type: {prdf.metadata.get('file_type', 'unknown')}")
    print(f"  Pages: {len(prdf.data['pages'])}")

    if path.suffix.lower() in ('.png', '.jpg', '.jpeg'):
        # Image — показываем что есть
        for i, page in enumerate(prdf.data['pages']):
            print(f"\nPage {i}:")
            for child in page.children:
                print(f"  {type(child).__name__}")
        # Применяем OCR
        extractor = Images2RegionsExtractor()
        extractor.extract(prdf)
        print("\nAfter OCR:")
        for i, page in enumerate(prdf.data['pages']):
            print(f"\nPage {i}:")
            for child in page.children:
                if hasattr(child, 'text'):
                    print(f"  {type(child).__name__}: {str(child.text)[:200]}")
                    if hasattr(child, 'children') and child.children:
                        for row in child.children:
                            for word in row.children:
                                conf = word.confidence
                                conf_str = f" ({conf:.0f}%)" if conf is not None else ""
                                print(f"    Word: '{word.text}'{conf_str}")
    else:
        print("PDF loaded (no pixel data for embedded images — OCR not applicable in v1)")
        print(f"  PageRDF metadata keys: {list(prdf.metadata.keys())}")


if __name__ == "__main__":
    main()

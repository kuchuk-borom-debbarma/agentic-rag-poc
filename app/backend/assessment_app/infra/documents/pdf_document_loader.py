"""PDF document loader adapter."""

from pathlib import Path

import pymupdf4llm

from assessment_app.services.rag.public.models import DocumentBlock


IGNORED_BOX_CLASSES = {"page-header", "page-footer", "picture"}


class PdfDocumentLoader:
    """Load layout-aware content blocks from a PDF file.

    Returns only useful layout boxes with non-empty text.
    Raises FileNotFoundError if the PDF does not exist.
    """

    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def load(self) -> list[DocumentBlock]:
        """Extract ordered layout blocks from all PDF pages."""
        if not self._pdf_path.exists():
            raise FileNotFoundError(f"Could not find PDF: {self._pdf_path}")
        pages = pymupdf4llm.to_markdown(str(self._pdf_path), page_chunks=True)
        blocks = []
        for page_index, page in enumerate(pages, start=1):
            page_text = page.get("text", "")
            for box in page.get("page_boxes", []):
                box_class = str(box.get("class", ""))
                if box_class in IGNORED_BOX_CLASSES:
                    continue
                position = box.get("pos")
                if not position or len(position) != 2:
                    continue
                text = page_text[position[0] : position[1]].strip()
                if text:
                    blocks.append(
                        DocumentBlock(
                            text=text,
                            box_class=box_class,
                            page_start=page_index,
                            page_end=page_index,
                        )
                    )
        return blocks

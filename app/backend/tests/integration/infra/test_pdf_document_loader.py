"""Integration-style tests for the layout-aware PDF loader."""

from pathlib import Path

from assessment_app.infra.documents import pdf_document_loader
from assessment_app.infra.documents.pdf_document_loader import PdfDocumentLoader


def test_pdf_document_loader_uses_layout_boxes_and_ignores_noise(monkeypatch, tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF fake")

    def fake_to_markdown(path: str, page_chunks: bool):
        assert path == str(pdf_path)
        assert page_chunks is True
        page_text = "HEADER\n# **1. Terms**\nBody text.\nPICTURE"
        return [
            {
                "text": page_text,
                "page_boxes": [
                    {"class": "page-header", "pos": _pos(page_text, "HEADER")},
                    {"class": "text", "pos": _pos(page_text, "# **1. Terms**")},
                    {"class": "text", "pos": _pos(page_text, "Body text.")},
                    {"class": "picture", "pos": _pos(page_text, "PICTURE")},
                ],
            }
        ]

    monkeypatch.setattr(pdf_document_loader.pymupdf4llm, "to_markdown", fake_to_markdown)

    blocks = PdfDocumentLoader(pdf_path).load()

    assert [block.text for block in blocks] == ["# **1. Terms**", "Body text."]
    assert [block.box_class for block in blocks] == ["text", "text"]
    assert [(block.page_start, block.page_end) for block in blocks] == [(1, 1), (1, 1)]


def _pos(text: str, needle: str) -> tuple[int, int]:
    start = text.index(needle)
    return start, start + len(needle)

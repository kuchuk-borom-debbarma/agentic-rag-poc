"""Semantic content chunking with reference re-indexing."""

from dataclasses import dataclass
import re

from assessment_app.services.rag.internal.ingestion.models import (
    ChunkedContent,
    ContentBlock,
    Reference,
    Section,
)

_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.DOTALL)


@dataclass(frozen=True)
class _TextSpan:
    start: int
    end: int
    text: str


class SemanticChunker:
    """Split content blocks into smaller semantic chunks."""

    def __init__(self, max_chars: int = 300) -> None:
        self._max_chars = max_chars

    def chunk(self, sections: list[Section]) -> list[ChunkedContent]:
        """Return semantic chunks for content blocks only."""
        chunks: list[ChunkedContent] = []
        for section in sections:
            for layout_index, block in enumerate(section.layout):
                if not isinstance(block, ContentBlock):
                    continue
                for chunk_index, span in enumerate(self._split_text(block.data)):
                    chunks.append(
                        ChunkedContent(
                            section_id=section.id,
                            layout_index=layout_index,
                            chunk_index=chunk_index,
                            text=span.text,
                            references=self._references_for_span(block.references, span),
                        )
                    )
        return chunks

    def _split_text(self, text: str) -> list[_TextSpan]:
        if len(text) < self._max_chars:
            return [_TextSpan(start=0, end=len(text), text=text)]

        spans: list[_TextSpan] = []
        for paragraph in self._paragraph_spans(text):
            if len(paragraph.text) < self._max_chars:
                spans.append(paragraph)
            else:
                spans.extend(self._sentence_spans(paragraph))
        return spans or [_TextSpan(start=0, end=len(text), text=text)]

    def _paragraph_spans(self, text: str) -> list[_TextSpan]:
        spans: list[_TextSpan] = []
        for match in re.finditer(r"\S.*?(?=\n\s*\n|$)", text, re.DOTALL):
            spans.append(self._trim_span(text, match.start(), match.end()))
        return [span for span in spans if span.text]

    def _sentence_spans(self, paragraph: _TextSpan) -> list[_TextSpan]:
        sentence_spans = [
            self._trim_span(paragraph.text, match.start(), match.end(), offset=paragraph.start)
            for match in _SENTENCE_RE.finditer(paragraph.text)
            if match.group(0).strip()
        ]
        if not sentence_spans:
            return [paragraph]

        combined: list[_TextSpan] = []
        current_start = sentence_spans[0].start
        current_end = sentence_spans[0].end
        for sentence in sentence_spans[1:]:
            candidate_text = paragraph.text[current_start - paragraph.start : sentence.end - paragraph.start].strip()
            if len(candidate_text) > self._max_chars:
                combined.append(self._trim_span(paragraph.text, current_start - paragraph.start, current_end - paragraph.start, paragraph.start))
                current_start = sentence.start
            current_end = sentence.end
        combined.append(self._trim_span(paragraph.text, current_start - paragraph.start, current_end - paragraph.start, paragraph.start))
        return combined

    def _trim_span(self, source: str, start: int, end: int, offset: int = 0) -> _TextSpan:
        while start < end and source[start].isspace():
            start += 1
        while end > start and source[end - 1].isspace():
            end -= 1
        return _TextSpan(start=offset + start, end=offset + end, text=source[start:end])

    def _references_for_span(self, references: list[Reference], span: _TextSpan) -> list[Reference]:
        chunk_references = []
        for reference in references:
            if reference.start_index < span.start or reference.end_index > span.end:
                continue
            chunk_references.append(
                Reference(
                    referenced_section_id=reference.referenced_section_id,
                    start_index=reference.start_index - span.start,
                    end_index=reference.end_index - span.start,
                )
            )
        return chunk_references

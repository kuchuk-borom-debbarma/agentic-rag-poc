"""Hierarchical-aware parser for mixed section layouts."""

from dataclasses import dataclass
import re

from assessment_app.services.rag.public.models import DocumentBlock
from assessment_app.services.rag.internal.ingestion.models import (
    ContentBlock,
    Reference,
    Section,
    SectionRefBlock,
)


_NUMBERED_HEADING_RE = re.compile(r"^#*\s*\**(\d+(?:\.\d+)*)\.?\s+(.+)$")
_BULLET_HEADING_RE = re.compile(r"^(\s*)-\s+(.+)$")
_REF_RE = re.compile(r"<ref>(.*?)</ref>|Section\s+(\d+(?:\.\d+)?)", re.IGNORECASE | re.DOTALL)
_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class _SectionContext:
    section: Section
    indent: int
    numbered_level: int | None


@dataclass(frozen=True)
class _PendingReference:
    block: ContentBlock
    label: str
    owner_index: int
    start_index: int
    end_index: int


class HierarchicalAwareParser:
    """Parse documents into sections that preserve mixed content/subsection order."""

    def parse(self, blocks: list[DocumentBlock]) -> list[Section]:
        """Return ordered sections with references resolved after full parse."""
        state = _ParserState()
        for block in blocks:
            for raw_line in block.text.splitlines():
                state.consume_line(raw_line)
        state.resolve_references()
        return state.sections


class _ParserState:
    def __init__(self) -> None:
        self.sections: list[Section] = []
        self._stack: list[_SectionContext] = []
        self._pending_references: list[_PendingReference] = []
        self._slug_counts: dict[str, int] = {}

    def consume_line(self, raw_line: str) -> None:
        line = raw_line.expandtabs(2).rstrip()
        if not line.strip():
            return

        numbered = self._numbered_heading(line)
        if numbered:
            section_number, title = numbered
            safe_title = title.replace("U.S. ", "US_DOT_ ").replace("U.K. ", "UK_DOT_ ").replace("e.g. ", "EG_DOT_ ").replace("i.e. ", "IE_DOT_ ")
            if ". " in safe_title:
                title_part, content_part = safe_title.split(". ", 1)
                title_part = title_part.replace("US_DOT_ ", "U.S. ").replace("UK_DOT_ ", "U.K. ").replace("EG_DOT_ ", "e.g. ").replace("IE_DOT_ ", "i.e. ")
                content_part = content_part.replace("US_DOT_ ", "U.S. ").replace("UK_DOT_ ", "U.K. ").replace("EG_DOT_ ", "e.g. ").replace("IE_DOT_ ", "i.e. ")
                self._add_numbered_section(section_number, title_part)
                self._add_content(content_part)
            else:
                self._add_numbered_section(section_number, title)
            return

        bullet = _BULLET_HEADING_RE.match(line)
        if bullet:
            self._add_bullet_section(indent=len(bullet.group(1)), title=bullet.group(2).strip())
            return

        self._add_content(line)

    def resolve_references(self) -> None:
        title_index = self._title_index()
        number_index = self._section_number_index()
        for pending in self._pending_references:
            referenced = number_index.get(pending.label)
            if not referenced:
                referenced = self._resolve_title(title_index, pending.label, pending.owner_index)
            if not referenced:
                continue
            pending.block.references.append(
                Reference(
                    referenced_section_id=referenced.id,
                    start_index=pending.start_index,
                    end_index=pending.end_index,
                )
            )

    def _add_numbered_section(self, section_number: str, title: str) -> None:
        level = section_number.count(".") + 1
        parent_context = next(
            (context for context in reversed(self._stack) if context.numbered_level == level - 1),
            None,
        )
        parent = parent_context.section if parent_context else None
        section = self._create_section(
            section_id=f"section_{section_number.replace('.', '_')}",
            title=self._clean_title(title, section_number),
            parent=parent,
        )
        self._stack = [context for context in self._stack if not context.numbered_level or context.numbered_level < level]
        self._stack.append(_SectionContext(section=section, indent=0, numbered_level=level))

    def _add_bullet_section(self, indent: int, title: str) -> None:
        parent_context = next((context for context in reversed(self._stack) if context.indent < indent), None)
        parent = parent_context.section if parent_context else None
        section = self._create_section(
            section_id=self._unique_slug_id(title),
            title=self._clean_title(title),
            parent=parent,
        )
        self._stack = [context for context in self._stack if context.indent < indent]
        self._stack.append(_SectionContext(section=section, indent=indent, numbered_level=None))

    def _create_section(self, section_id: str, title: str, parent: Section | None) -> Section:
        section = Section(id=section_id, title=title, layout=[], parent=parent.id if parent else None)
        self.sections.append(section)
        if parent:
            parent.layout.append(SectionRefBlock(section_id=section.id))
        return section

    def _add_content(self, line: str) -> None:
        owner = self._owner_for_content(line)
        clean_text, pending_references = self._clean_references(line.strip(), self.sections.index(owner))
        if not clean_text:
            return
        block = ContentBlock(data=clean_text)
        owner.layout.append(block)
        self._pending_references.extend(
            _PendingReference(
                block=block,
                label=label,
                owner_index=owner_index,
                start_index=start_index,
                end_index=end_index,
            )
            for label, owner_index, start_index, end_index in pending_references
        )

    def _owner_for_content(self, line: str) -> Section:
        if not self._stack:
            if self.sections and self.sections[0].id == "section_front_matter":
                return self.sections[0]
            return self._create_section("section_front_matter", "Front Matter", None)
        indent = len(line) - len(line.lstrip())
        return next((context.section for context in reversed(self._stack) if context.indent <= indent), self._stack[-1].section)

    def _clean_references(self, text: str, owner_index: int) -> tuple[str, list[tuple[str, int, int, int]]]:
        clean_text = ""
        pending: list[tuple[str, int, int, int]] = []
        cursor = 0
        for match in _REF_RE.finditer(text):
            if match.group(1):  # <ref> tag matched
                clean_text += text[cursor : match.start()]
                label = re.sub(r"\s+", " ", match.group(1)).strip()
                start_index = len(clean_text)
                clean_text += label
                end_index = len(clean_text)
                if label:
                    pending.append((label, owner_index, start_index, end_index))
            else:  # Section X.Y matched
                clean_text += text[cursor : match.start()]
                label = match.group(2).strip()
                start_index = len(clean_text)
                clean_text += match.group(0)  # Keep the text "Section X.Y"
                end_index = len(clean_text)
                if label:
                    pending.append((label, owner_index, start_index, end_index))
            cursor = match.end()
        clean_text += text[cursor:]
        return clean_text.strip(), pending

    def _title_index(self) -> dict[str, list[tuple[int, Section]]]:
        title_index: dict[str, list[tuple[int, Section]]] = {}
        for index, section in enumerate(self.sections):
            title_index.setdefault(self._normalise(section.title), []).append((index, section))
        return title_index

    def _section_number_index(self) -> dict[str, Section]:
        number_index: dict[str, Section] = {}
        for section in self.sections:
            if section.id.startswith("section_") and section.id != "section_front_matter":
                num = section.id.replace("section_", "").replace("_", ".")
                number_index[num] = section
        return number_index

    def _resolve_title(
        self,
        title_index: dict[str, list[tuple[int, Section]]],
        label: str,
        owner_index: int,
    ) -> Section | None:
        candidates = [(index, section) for index, section in title_index.get(self._normalise(label), []) if index != owner_index]
        later = [(index, section) for index, section in candidates if index > owner_index]
        if later:
            return min(later, key=lambda item: item[0])[1]
        earlier = [(index, section) for index, section in candidates if index < owner_index]
        if earlier:
            return max(earlier, key=lambda item: item[0])[1]
        return None

    def _numbered_heading(self, line: str) -> tuple[str, str] | None:
        match = _NUMBERED_HEADING_RE.match(line.strip())
        if not match:
            return None
        return match.group(1), match.group(2)

    def _unique_slug_id(self, title: str) -> str:
        base = self._normalise(title) or "section"
        count = self._slug_counts.get(base, 0) + 1
        self._slug_counts[base] = count
        suffix = "" if count == 1 else f"_{count}"
        return f"section_{base}{suffix}"

    def _clean_title(self, title: str, section_number: str | None = None) -> str:
        cleaned = title.replace("*", "").replace("#", "")
        if section_number:
            cleaned = re.sub(rf"^{re.escape(section_number)}\.?\s*", "", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip().rstrip(".")

    def _normalise(self, value: str) -> str:
        slug = _NON_SLUG_RE.sub("_", value.strip().lower()).strip("_")
        return slug

"""Unit tests for hierarchical-aware ingestion parsing."""

import pytest

from assessment_app.services.rag.public.models import DocumentBlock
from assessment_app.services.rag.internal.ingestion.models import ContentBlock, Reference, SectionRefBlock
from assessment_app.services.rag.internal.ingestion.parser import HierarchicalAwareParser
from assessment_app.services.rag.internal.ingestion.service_impl import DefaultIngestionParsingService
from assessment_app.services.rag.internal.ingestion.validator import StructureValidationError, StructureValidator


def test_parser_preserves_parent_child_parent_layout():
    sections = _parse(
        "\n".join(
            [
                "- Foo",
                "This is foo content.",
                "  - Bar",
                "  Bar content here.",
                "More foo content. See <ref>Bar</ref> for details.",
            ]
        )
    )

    foo, bar = sections
    assert foo.title == "Foo"
    assert bar.parent == foo.id
    assert [block.type for block in foo.layout] == ["content", "section-ref", "content"]
    assert isinstance(foo.layout[1], SectionRefBlock)
    assert foo.layout[1].section_id == bar.id
    assert _content(foo.layout[2]).data == "More foo content. See Bar for details."


def test_parser_resolves_past_reference():
    sections = _parse("- Bar\nBar content.\n- Foo\nSee <ref>Bar</ref> now.")

    foo = sections[1]
    block = _content(foo.layout[0])
    assert block.data == "See Bar now."
    assert block.references[0].referenced_section_id == sections[0].id
    assert block.references[0].start_index == 4
    assert block.references[0].end_index == 7


def test_parser_resolves_future_reference():
    sections = _parse("- Foo\nSee <ref>Bar</ref> later.\n- Bar\nBar content.")

    block = _content(sections[0].layout[0])
    assert block.data == "See Bar later."
    assert block.references[0].referenced_section_id == sections[1].id


def test_parser_resolves_duplicate_title_to_nearest_later_section():
    sections = _parse(
        "\n".join(
            [
                "- Bar",
                "Old bar.",
                "- Foo",
                "See <ref>Bar</ref> later.",
                "- Bar",
                "New bar.",
            ]
        )
    )

    block = _content(sections[1].layout[0])
    assert block.references[0].referenced_section_id == sections[2].id


def test_parser_strips_unknown_reference_without_reference_record():
    sections = _parse("- Foo\nSee <ref>Missing</ref> later.")

    block = _content(sections[0].layout[0])
    assert block.data == "See Missing later."
    assert block.references == []


def test_parser_tracks_numbered_hierarchy():
    sections = _parse("1. Terms\nIntro.\n1.1 Accounts\nAccount content.\n1.1.1 Users\nUser content.")

    terms, accounts, users = sections
    assert accounts.parent == terms.id
    assert users.parent == accounts.id
    assert [block.type for block in terms.layout] == ["content", "section-ref"]
    assert [block.type for block in accounts.layout] == ["content", "section-ref"]


def test_parser_normalizes_pymupdf_markdown_numbered_heading():
    sections = _parse("# **1. Terms and Conditions.**\nBody.")

    assert sections[0].id == "section_1"
    assert sections[0].title == "Terms and Conditions"


def test_parser_splits_inline_content_from_numbered_title():
    sections = _parse("1.2 Third-Party Content. Third-Party Content may be used by you at your election.")

    assert sections[0].id == "section_1_2"
    assert sections[0].title == "Third-Party Content"
    assert len(sections[0].layout) == 1
    assert _content(sections[0].layout[0]).data == "Third-Party Content may be used by you at your election."


def test_parser_tracks_indented_bullet_hierarchy():
    sections = _parse("- Foo\n  - Bar\n  Bar content.\n- Baz\nBaz content.")

    foo, bar, baz = sections
    assert bar.parent == foo.id
    assert baz.parent is None
    assert [block.type for block in foo.layout] == ["section-ref"]
    assert _content(bar.layout[0]).data == "Bar content."


def test_ingestion_parse_service_uses_loader_and_parser():
    service = DefaultIngestionParsingService(
        document_loader=_FakeDocumentLoader(),
        parser=HierarchicalAwareParser(),
    )

    sections = service.parse()

    assert [section.title for section in sections] == ["Foo", "Bar"]
    assert sections[1].parent == sections[0].id


def test_validator_rejects_missing_child_section():
    sections = _parse("- Foo\nFoo content.")
    sections[0].layout.append(SectionRefBlock(section_id="section_missing"))

    with pytest.raises(StructureValidationError):
        StructureValidator().validate(sections)


def test_validator_rejects_missing_reference_target():
    sections = _parse("- Foo\nSee <ref>Bar</ref>.")
    block = _content(sections[0].layout[0])
    block.references.append(Reference(referenced_section_id="section_missing", start_index=4, end_index=7))

    with pytest.raises(StructureValidationError):
        StructureValidator().validate(sections)


def _parse(text: str):
    return HierarchicalAwareParser().parse(
        [DocumentBlock(text=text, box_class="text", page_start=1, page_end=1)]
    )


def _content(block: object) -> ContentBlock:
    assert isinstance(block, ContentBlock)
    return block


class _FakeDocumentLoader:
    def load(self) -> list[DocumentBlock]:
        return [DocumentBlock(text="- Foo\n  - Bar\n  Bar content.", box_class="text", page_start=1, page_end=1)]

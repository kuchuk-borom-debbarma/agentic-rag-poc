import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf4llm


DOCUMENT_ID = "aws_customer_agreement"
DOCUMENT_TITLE = "AWS Customer Agreement"
PROCESSOR_VERSION = "document_graph.v1"

MAJOR_SEC_RE = re.compile(r"^#*\s*\**(\d+)\.\s+(.+)")
MINOR_SEC_RE = re.compile(r"^#*\s*\**(\d+\.\d+)\s+(.+)")
SECTION_REF_RE = re.compile(r"Section\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
IGNORED_BOX_CLASSES = {"page-header", "page-footer", "picture"}


def log(step, message):
    print(f"[Step 1] {step}: {message}")


def clean_text(text):
    return text.replace("*", "").replace("#", "").strip()


def normalize_title(raw_title):
    title = clean_text(raw_title)
    title = re.sub(r"^\d+(?:\.\d+)?\.?\s*", "", title)
    protected = {
        "U.S.": "US_DOT_",
        "U.K.": "UK_DOT_",
        "e.g.": "EG_DOT_",
        "i.e.": "IE_DOT_",
    }
    for original, replacement in protected.items():
        title = title.replace(original, replacement)
    title = title.split(". ", 1)[0]
    for original, replacement in protected.items():
        title = title.replace(replacement, original)
    return title.strip().rstrip(".")


def section_id(section_number):
    if section_number == "front_matter":
        return "section_front_matter"
    return f"section_{section_number.replace('.', '_')}"


def detect_section(text):
    cleaned = clean_text(text)
    major = MAJOR_SEC_RE.match(text)
    if major:
        return {
            "section_number": major.group(1),
            "title": normalize_title(cleaned),
            "level": 1,
        }

    minor = MINOR_SEC_RE.match(text)
    if minor:
        return {
            "section_number": minor.group(1),
            "title": normalize_title(cleaned),
            "level": 2,
        }

    return None


def source_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def extract_blocks(pdf_path):
    log("extract", f"Parsing PDF with layout boxes: {pdf_path}")
    pages = pymupdf4llm.to_markdown(pdf_path, page_chunks=True)
    blocks = []

    for page_index, page in enumerate(pages, start=1):
        page_text = page.get("text", "")
        for box in page.get("page_boxes", []):
            box_class = box.get("class", "")
            if box_class in IGNORED_BOX_CLASSES:
                continue

            pos = box.get("pos")
            if not pos or len(pos) != 2:
                continue

            text = page_text[pos[0]:pos[1]].strip()
            if not text:
                continue

            blocks.append(
                {
                    "text": text,
                    "box_class": box_class,
                    "page_start": page_index,
                    "page_end": page_index,
                }
            )

    log("extract", f"Collected {len(blocks)} content blocks")
    return blocks


def ensure_section(sections_by_id, section_order, section_number, title, level, parent_section_id=None):
    sid = section_id(section_number)
    if sid not in sections_by_id:
        sections_by_id[sid] = {
            "section_id": sid,
            "section_number": section_number,
            "title": title,
            "level": level,
            "parent_section_id": parent_section_id,
            "child_section_ids": [],
            "chunk_ids": [],
            "order": len(section_order),
        }
        section_order.append(sid)

    section = sections_by_id[sid]
    if parent_section_id and not section["parent_section_id"]:
        section["parent_section_id"] = parent_section_id

    if parent_section_id:
        parent = sections_by_id[parent_section_id]
        if sid not in parent["child_section_ids"]:
            parent["child_section_ids"].append(sid)

    return sid


def build_document_graph(blocks, pdf_path):
    log("build", "Creating Document -> Section -> Chunk graph model")
    sections_by_id = {}
    section_order = []
    current_major_section_id = None
    current_section_id = ensure_section(
        sections_by_id,
        section_order,
        "front_matter",
        "Front Matter",
        0,
    )
    chunks = []

    for order, block in enumerate(blocks):
        text = block["text"]
        detected = detect_section(text)
        chunk_type = "section_body"

        if detected:
            sid = ensure_section(
                sections_by_id,
                section_order,
                detected["section_number"],
                detected["title"],
                detected["level"],
                parent_section_id=current_major_section_id if detected["level"] > 1 else None,
            )
            current_section_id = sid
            chunk_type = "section_heading"

            if detected["level"] == 1:
                current_major_section_id = sid
            elif not current_major_section_id:
                current_major_section_id = sid
        elif current_section_id == "section_front_matter":
            chunk_type = "front_matter"

        section = sections_by_id[current_section_id]
        chunk_id = f"chunk_{order:04d}"
        chunk = {
            "chunk_id": chunk_id,
            "section_id": current_section_id,
            "section_number": section["section_number"],
            "text": text,
            "chunk_type": chunk_type,
            "order": order,
            "page_start": block["page_start"],
            "page_end": block["page_end"],
            "previous_chunk_id": f"chunk_{order - 1:04d}" if order > 0 else None,
            "next_chunk_id": None,
            "referenced_section_ids": [],
            "referenced_by_chunk_ids": [],
        }
        if chunks:
            chunks[-1]["next_chunk_id"] = chunk_id
        chunks.append(chunk)
        section["chunk_ids"].append(chunk_id)

    section_number_to_id = {
        section["section_number"]: section["section_id"]
        for section in sections_by_id.values()
        if section["section_number"] != "front_matter"
    }
    wire_references(chunks, section_number_to_id)

    document = {
        "document_id": DOCUMENT_ID,
        "title": DOCUMENT_TITLE,
        "source_path": "resources/AWS Customer Agreement.pdf",
        "source_type": "pdf",
        "source_hash": source_hash(pdf_path),
        "processor_version": PROCESSOR_VERSION,
    }
    graph = {
        "document": document,
        "sections": [sections_by_id[sid] for sid in section_order],
        "chunks": chunks,
    }
    validate_graph(graph)
    log("build", f"Built {len(graph['sections'])} sections and {len(chunks)} chunks")
    return graph


def wire_references(chunks, section_number_to_id):
    log("references", "Resolving text references to canonical Section nodes")
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}

    for chunk in chunks:
        seen_targets = set()
        for ref_number in SECTION_REF_RE.findall(chunk["text"]):
            target_section_id = section_number_to_id.get(ref_number)
            if not target_section_id or target_section_id in seen_targets:
                continue
            if target_section_id == chunk["section_id"]:
                continue

            chunk["referenced_section_ids"].append(target_section_id)
            seen_targets.add(target_section_id)

    inbound = {chunk["chunk_id"]: set() for chunk in chunks}
    section_chunks = {}
    for chunk in chunks:
        section_chunks.setdefault(chunk["section_id"], []).append(chunk["chunk_id"])

    for source in chunks:
        for target_section_id in source["referenced_section_ids"]:
            for target_chunk_id in section_chunks.get(target_section_id, []):
                inbound[target_chunk_id].add(source["chunk_id"])

    for chunk_id, source_ids in inbound.items():
        chunks_by_id[chunk_id]["referenced_by_chunk_ids"] = sorted(source_ids)


def validate_graph(graph):
    errors = []
    document = graph.get("document") or {}
    sections = graph.get("sections") or []
    chunks = graph.get("chunks") or []
    section_ids = {section["section_id"] for section in sections}
    chunk_ids = {chunk["chunk_id"] for chunk in chunks}
    chunk_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}

    if not document.get("document_id"):
        errors.append("document.document_id missing")

    for section in sections:
        parent_id = section.get("parent_section_id")
        if parent_id and parent_id not in section_ids:
            errors.append(f"{section['section_id']} parent_section_id missing: {parent_id}")
        for child_id in section.get("child_section_ids", []):
            if child_id not in section_ids:
                errors.append(f"{section['section_id']} child_section_id missing: {child_id}")
        for chunk_id in section.get("chunk_ids", []):
            if chunk_id not in chunk_ids:
                errors.append(f"{section['section_id']} chunk_id missing: {chunk_id}")

    orders = [chunk["order"] for chunk in chunks]
    if sorted(orders) != list(range(len(chunks))):
        errors.append("chunk order must be unique and continuous from 0")

    expected_backrefs = {chunk["chunk_id"]: set() for chunk in chunks}
    section_to_chunks = {}
    for chunk in chunks:
        section_to_chunks.setdefault(chunk["section_id"], []).append(chunk["chunk_id"])

    for chunk in chunks:
        section_id_value = chunk.get("section_id")
        if section_id_value not in section_ids:
            errors.append(f"{chunk['chunk_id']} section_id missing: {section_id_value}")

        previous_id = chunk.get("previous_chunk_id")
        next_id = chunk.get("next_chunk_id")
        if previous_id and previous_id not in chunk_ids:
            errors.append(f"{chunk['chunk_id']} previous_chunk_id missing: {previous_id}")
        if next_id and next_id not in chunk_ids:
            errors.append(f"{chunk['chunk_id']} next_chunk_id missing: {next_id}")

        for ref_section_id in chunk.get("referenced_section_ids", []):
            if ref_section_id not in section_ids:
                errors.append(f"{chunk['chunk_id']} referenced_section_id missing: {ref_section_id}")
                continue
            for target_chunk_id in section_to_chunks.get(ref_section_id, []):
                expected_backrefs[target_chunk_id].add(chunk["chunk_id"])

    for chunk in chunks:
        actual = set(chunk.get("referenced_by_chunk_ids", []))
        expected = expected_backrefs[chunk["chunk_id"]]
        missing = expected - actual
        extra = actual - expected
        if missing:
            errors.append(f"{chunk['chunk_id']} missing referenced_by_chunk_ids: {sorted(missing)}")
        if extra:
            errors.append(f"{chunk['chunk_id']} extra referenced_by_chunk_ids: {sorted(extra)}")
        for referrer_id in actual:
            if referrer_id not in chunk_ids:
                errors.append(f"{chunk['chunk_id']} referenced_by_chunk_id missing: {referrer_id}")

    if errors:
        joined = "\n- ".join(errors)
        raise ValueError(f"Graph validation failed:\n- {joined}")

    return True


def load_graph(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_graph(graph, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(graph, handle, indent=2)
    log("write", f"Saved graph JSON to {output_path}")


def default_paths():
    step_dir = Path(__file__).resolve().parent
    repo_root = step_dir.parents[1]
    return {
        "pdf": repo_root / "resources" / "AWS Customer Agreement.pdf",
        "output": step_dir / "document_graph.json",
    }


def main():
    paths = default_paths()
    parser = argparse.ArgumentParser(description="Build and validate document graph JSON.")
    parser.add_argument("--pdf", default=str(paths["pdf"]), help="Source PDF path")
    parser.add_argument("--output", default=str(paths["output"]), help="Output graph JSON path")
    parser.add_argument("--validate-only", action="store_true", help="Validate an existing graph JSON")
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    if args.validate_only:
        log("validate", f"Validating existing graph JSON: {output_path}")
        validate_graph(load_graph(output_path))
        log("validate", "Graph invariants OK")
        return

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"Could not find {pdf_path}")

    blocks = extract_blocks(pdf_path)
    graph = build_document_graph(blocks, pdf_path)
    write_graph(graph, output_path)
    log("done", "Document graph build complete")


if __name__ == "__main__":
    main()

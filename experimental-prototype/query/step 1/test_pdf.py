import pymupdf4llm
pages = pymupdf4llm.to_markdown("../../resources/AWS Customer Agreement.pdf", page_chunks=True)
for box in pages[0].get("page_boxes", [])[:10]:
    pos = box.get("pos")
    if pos:
        print(box.get("class", "no-class"), repr(pages[0].get("text", "")[pos[0]:pos[1]]))

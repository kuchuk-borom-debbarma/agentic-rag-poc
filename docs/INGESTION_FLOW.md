# RAG Ingestion Flow Explained

This document outlines the 5 detailed stages of our ingestion pipeline, demonstrating the problems solved, the data structures used, and providing mapped examples for each phase.

---

## Stage 1: Hierarchical Aware Parsing

### The Problem
Documents have sections that contain:
- Content
- Subsections
- More content (after subsections)
- References to other sections (inline, by name)

Most standard document parsers can't handle this mixed pattern. They read top-to-bottom as a flat string. We need a structure that preserves hierarchy and cross-references.

### Quick Example
```text
- Foo
This is foo content.
  - Bar
  Bar content here.
More foo content. See <ref>Bar</ref> for details.
```

Notice:
- `Foo` has content, then a subsection, then more content.
- "See Bar for details" is an inline reference that needs to be tracked.

### The Data Structure
```typescript
type Section = {
  id: string;
  title: string;
  layout: LayoutBlock[];
  parent: string | null;
};

type LayoutBlock = ContentBlock | SectionRefBlock;

type ContentBlock = {
  type: "content";
  data: string;
  references: Reference[];
};

type SectionRefBlock = {
  type: "section-ref";
  sectionId: string;
};

type Reference = {
  referencedSectionId: string;
  startIndex: number;
  endIndex: number;
};
```

### Mapped Example
```json
[
  {
    "id": "1",
    "title": "Foo",
    "layout": [
      {
        "type": "content",
        "data": "This is foo content.",
        "references": []
      },
      { "type": "section-ref", "sectionId": "2" },
      {
        "type": "content",
        "data": "More foo content. See Bar for details.",
        "references": [
          {
            "referencedSectionId": "2",
            "startIndex": 25,
            "endIndex": 28
          }
        ]
      }
    ],
    "parent": null
  },
  {
    "id": "2",
    "title": "Bar",
    "layout": [
      {
        "type": "content",
        "data": "Bar content here.",
        "references": []
      }
    ],
    "parent": "1"
  }
]
```

### Key Points
- By resolving layout into blocks, we know exactly when a subsection occurs relative to text.
- Inline references are resolved to exact `section_id` pointers, solving the issue of loose textual references.
- **What is not tackled:** Tables and images are flattened or ignored. This parser exclusively optimizes for nested text hierarchies.

---

## Stage 2: Semantic Chunking

### The Problem
Fixed-size chunking (e.g., splitting every 500 characters) blindly tears sentences in half and destroys meaning. Furthermore, when a large paragraph is split, any inline reference index offsets become invalid relative to the new shorter chunk string.

### Quick Example
```text
Section 2.1 covers late payments. A 5% fee is applied.
```
*Bad Chunking:* `Section 2.1 covers late pay` | `ments. A 5% fee is applied.`
*Good Chunking:* `Section 2.1 covers late payments.` | `A 5% fee is applied.`

### The Data Structure
```typescript
type ChunkedContent = {
  sectionId: string;
  layoutIndex: number;
  chunkIndex: number;
  text: string;
  references: Reference[];
  embedding?: number[];
};
```

### Mapped Example
Given a long `ContentBlock` from `Section 1`:
```json
[
  {
    "sectionId": "1",
    "layoutIndex": 0,
    "chunkIndex": 0,
    "text": "This is the first sentence.",
    "references": []
  },
  {
    "sectionId": "1",
    "layoutIndex": 0,
    "chunkIndex": 1,
    "text": "See Bar for details.",
    "references": [
      {
        "referencedSectionId": "2",
        "startIndex": 4,
        "endIndex": 7
      }
    ]
  }
]
```

### Key Points
- Sentences are kept completely intact. If a paragraph is too long, we split at punctuation boundaries (`.`, `!`, `?`).
- References are re-indexed. The `startIndex` is dynamically recalculated relative to the start of the new `chunkIndex` rather than the original `ContentBlock`.
- Every chunk retains its `sectionId`, solving the issue of a chunk losing its context.

---

## Stage 3: Graph Navigation Building

### The Problem
At query time, when we retrieve a chunk, we often need to fetch the chunks immediately before/after it, or its parent section. Doing semantic vector searches to find these is slow and inaccurate. We need deterministic traversal.

### Quick Example
If chunk `B` is retrieved, we instantly want to find `A` (previous), `C` (next), and `Parent Section` without hitting ChromaDB.

### The Data Structure
```typescript
type DocumentChunk = {
  chunkId: string;
  text: string;
  sectionId: string;
  parentSectionId: string | null;
  previousChunkId: string | null;
  nextChunkId: string | null;
  referencedSectionIds: string[];
};

type Graph = {
  chunks: DocumentChunk[];
};
```

### Mapped Example
```json
{
  "chunks": [
    {
      "chunkId": "chunk_0",
      "text": "This is foo content.",
      "sectionId": "1",
      "parentSectionId": null,
      "previousChunkId": null,
      "nextChunkId": "chunk_1",
      "referencedSectionIds": []
    },
    {
      "chunkId": "chunk_1",
      "text": "More foo content. See Bar for details.",
      "sectionId": "1",
      "parentSectionId": null,
      "previousChunkId": "chunk_0",
      "nextChunkId": null,
      "referencedSectionIds": ["2"]
    }
  ]
}
```

### Key Points
- The graph maps are generated natively from the parsed sequence.
- This solves the hallucination issue: if an LLM needs surrounding context, we follow the `nextChunkId` or `parentSectionId` pointers natively.

---

## Stage 4: Graph Persistence (SQLite)

### The Problem
We have a highly connected graph in memory, but running a dedicated graph database like Neo4j introduces massive operational overhead for a simple RAG deployment. We need a lightweight way to store and query these relationships.

### Quick Example
`SELECT * FROM chunks WHERE chunk_id = 'chunk_1'` -> Instantly yields the chunk with its relational pointers.

### The Data Structure
```sql
CREATE TABLE chunks (
  chunk_id TEXT PRIMARY KEY,
  text TEXT,
  section_id TEXT,
  parent_section_id TEXT,
  previous_chunk_id TEXT,
  next_chunk_id TEXT,
  referenced_section_ids TEXT
);
```

### Mapped Example
```json
[
  {
    "row_id": 1,
    "chunk_id": "chunk_1",
    "parent_section_id": "section_1",
    "next_chunk_id": "chunk_2",
    "referenced_section_ids": "[\"section_2\"]"
  }
]
```

### Key Points
- SQLite is fast, local, and requires zero setup.
- Relational joins and indexed lookups provide sub-millisecond retrieval of parent or neighbor chunks.
- SQLite also powers lexical retrieval over chunk text, section titles, parent titles, and section numbers.
- Source snippets use document/section-aware ordering so citations are stable across sections.
- **What is not tackled:** Multi-document graphs. The current SQLite schema assumes a continuous linear sequence for a single document.

---

## Stage 5: Vector Persistence (ChromaDB)

### The Problem
While SQLite handles deterministic relationships, it cannot perform semantic similarity search ("Which chunk is conceptually similar to this user query?"). We need a dedicated vector database to store the dense embeddings generated in Stage 2 alongside the text.

### Quick Example
User asks: "What happens if I don't pay?"
ChromaDB calculates cosine similarity across thousands of vectors and returns `chunk_45` which talks about "Late Fees".

### The Data Structure
```typescript
type VectorStoreRecord = {
  id: string; // matches chunk_id
  embedding: number[];
  document: string;
  metadata: {
    section_id: string;
    section_title: string;
  };
};
```

### Mapped Example
```json
{
  "ids": ["chunk_1"],
  "embeddings": [[0.112, -0.045, 0.887, "..."]],
  "documents": ["More foo content. See Bar for details."],
  "metadatas": [{"section_id": "1", "section_title": "Foo"}]
}
```

### Key Points
- ChromaDB handles purely semantic retrieval.
- Crucially, the `id` in ChromaDB maps exactly to `chunk_id` in SQLite. When ChromaDB finds a semantic match, the system uses that `id` to instantly pull the full relational context from SQLite.
- **Embedding Batching:** The ingestion pipeline batches embedding generation requests (e.g. 50 chunks at a time) to prevent local LLM servers like Ollama from crashing under high parallel load.
- **SSE Progress:** The entire ingestion process emits Server-Sent Events (SSE) so the React UI can display real-time parsing, chunking, and embedding progress animations.
- The frontend Graph tab reads paged graph visualization data from the ingestion service. The endpoint defaults to 120 nodes, caps at 300, and only returns edges whose endpoints are visible in the current page.
- **What is not tackled:** Incremental vector upserts. The current endpoint drops and recreates the collection entirely.

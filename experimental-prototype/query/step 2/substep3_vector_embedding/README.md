# Sub-step 3: LM Studio Embeddings

## Goal

Embed all Neo4j `Chunk` nodes using LM Studio's OpenAI-compatible HTTP API and store vectors as `EmbeddingChunk` nodes.

Graph shape:

```text
Chunk -[:HAS_EMBEDDING]-> EmbeddingChunk
```

## Approach

`embed_children.py` does the full vector pass:

1. Loads `.env`.
2. Normalizes `OPENAI_EMBEDDING_BASE_URL`.
3. Checks LM Studio `/models`.
4. Sends one test `/embeddings` request and detects vector dimension.
5. Fetches all `Chunk` nodes ordered by `order`.
6. Semantically splits each chunk to build the complete embedding work list.
7. Recreates the Neo4j vector index.
8. Embeds each task and stores an `EmbeddingChunk`.
9. Shows progress with a replacing terminal line when possible.

## Environment

Expected `.env` keys:

```bash
OPENAI_EMBEDDING_BASE_URL=http://localhost:1234/v1
OPENAI_EMBEDDING_MODEL=your-loaded-embedding-model
OPENAI_EMBEDDING_API_KEY=lm-studio
```

The base URL may omit `/v1`; the script adds it automatically.

## Progress UI

TTY output updates one line in place:

```text
[7/8] Embedding via LM Studio | 128/482 done | 354 left | ########---------- | chunk_0042 -> emb_chunk_0042_00
```

Non-TTY output prints compact periodic progress lines.

## Troubleshooting LM Studio

If the script says LM Studio is unreachable:

- Start LM Studio Developer server.
- Load an embedding model.
- Confirm the model name matches `OPENAI_EMBEDDING_MODEL`.
- If using a LAN IP like `192.168.x.x`, ensure both machines are on the same network.
- Confirm LM Studio allows LAN connections.
- Try `http://localhost:1234/v1` if running locally.

## Run

Health check only:

```bash
../../../venv/bin/python embed_children.py --health-only
```

Full embedding pass:

```bash
../../../venv/bin/python embed_children.py
```

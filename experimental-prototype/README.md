# Experimental Prototype

Welcome to the `experimental-prototype` directory! 

This folder contains the exploratory code and isolated components that I used to test and evaluate the core flow logic for the RAG pipeline before integrating them into the final `app/` architecture. 

## What is this?
Building a deterministic, hallucination-free Agentic RAG system requires extensive trial and error. Before finalizing the production architecture (which uses LangChain, Pydantic, and FastAPI), I needed a sandbox to prove that the core logic actually worked. 

This prototype directory is where **the vast majority of the time was spent** during the assessment. It contains the raw scripts where I:
- Tested the `HierarchicalAwareParser` logic to ensure subsections didn't lose their parent context.
- Validated the 300-character `SemanticChunker` to ensure sentences weren't split.
- Built the initial SQLite Graph map to prove deterministic graph traversal could replace pure vector semantic search.
- Tuned the LLM "Judge" prompt loops to fetch parent/neighbor chunks accurately.

## Why keep it here?
I wanted to include this in the submission to provide full transparency into my engineering process. While the final `app/` directory represents the clean, refactored, and dependency-inverted end product, this prototype directory shows the iterative problem-solving and rigorous testing of the core "flow logic" that makes the final app so reliable.

Please note that this code is meant for internal testing and might not be as polished or cleanly structured as the final submission code in the root `app/` directory!

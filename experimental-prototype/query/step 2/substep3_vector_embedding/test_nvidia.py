import os
from langchain_openai import OpenAIEmbeddings

api_key = os.environ.get("OPENAI_EMBEDDING_API_KEY") or os.environ.get("NVIDIA_API_KEY")
if not api_key:
    raise SystemExit("Set OPENAI_EMBEDDING_API_KEY or NVIDIA_API_KEY before running this smoke script.")
base_url = "https://integrate.api.nvidia.com/v1"
model = "nvidia/nv-embedqa-e5-v5"

emb = OpenAIEmbeddings(api_key=api_key, base_url=base_url, model=model)
try:
    print(emb.embed_query("Hello world"))
    print("Success query")
except Exception as e:
    print(e)

try:
    print(emb.embed_documents(["Hello world"]))
    print("Success docs")
except Exception as e:
    print(e)

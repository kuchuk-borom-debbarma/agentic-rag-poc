from langchain_huggingface import HuggingFaceEmbeddings
try:
    emb = HuggingFaceEmbeddings(model_name="/Users/kuchukboromdebbarma/.lmstudio/models/mlx-community/Qwen3-Embedding-4B-4bit-DWQ")
    print("DIMENSION:", len(emb.embed_query("Hello")))
except Exception as e:
    print("ERROR:", e)

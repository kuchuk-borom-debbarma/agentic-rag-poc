import mlx.core as mx
from mlx_lm import load
model, tokenizer = load("/Users/kuchukboromdebbarma/.lmstudio/models/mlx-community/Qwen3-Embedding-4B-4bit-DWQ")
tokens = tokenizer.encode("Hello world")
x = mx.array([tokens])
print("Shape of x:", x.shape)
hidden = model.model(x)
print("Shape of hidden:", hidden.shape)
import mlx.nn as nn
# Most embedding models do mean pooling or last token pooling.
# For last token pooling (decoder-only architectures):
emb = hidden[:, -1, :]
emb = emb / mx.linalg.norm(emb, axis=-1, keepdims=True)
print("Shape of emb:", emb.shape)

from mlx_lm import load
model, tokenizer = load("/Users/kuchukboromdebbarma/.lmstudio/models/mlx-community/Qwen3-Embedding-4B-4bit-DWQ")
print(dir(model))
print(model)
